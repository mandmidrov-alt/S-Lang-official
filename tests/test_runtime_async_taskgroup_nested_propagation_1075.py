from __future__ import annotations

import asyncio

import pytest

import slang.stdlib_runtime as runtime


def _flatten(group: BaseExceptionGroup) -> list[BaseException]:
    leaves: list[BaseException] = []
    for error in group.exceptions:
        if isinstance(error, BaseExceptionGroup):
            leaves.extend(_flatten(error))
        else:
            leaves.append(error)
    return leaves


def test_nested_taskgroup_preserves_exception_group_structure_and_identity():
    first = ValueError("inner first failure")
    second = LookupError("inner second failure")

    async def scenario():
        async def fail(error: Exception):
            await asyncio.sleep(0)
            raise error

        with pytest.raises(ExceptionGroup) as caught:
            async with asyncio.TaskGroup() as outer:
                async def nested_group():
                    async with asyncio.TaskGroup() as inner:
                        inner.create_task(fail(first))
                        inner.create_task(fail(second))

                outer.create_task(nested_group())
        return caught.value

    group = asyncio.run(scenario())
    assert len(group.exceptions) == 1
    nested = group.exceptions[0]
    assert isinstance(nested, ExceptionGroup)
    assert len(nested.exceptions) == 2
    assert nested.exceptions[0] is first
    assert nested.exceptions[1] is second
    assert _flatten(group) == [first, second]


def test_nested_group_errors_do_not_duplicate_during_parent_context_cleanup():
    first = RuntimeError("nested task failure")
    cleanup = OSError("sibling cleanup failure")

    async def scenario():
        with runtime.runtime_execution_context(max_events=4) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            sibling_started = asyncio.Event()

            async def nested_failing_child():
                with runtime.runtime_execution_context(max_events=2):
                    runtime.execute_registered_stdlib("current_directory", [])
                    await sibling_started.wait()
                    raise first

            async def sibling_with_cleanup_failure():
                with runtime.runtime_execution_context(max_events=2):
                    runtime.execute_registered_stdlib("current_directory", [])
                    sibling_started.set()
                    try:
                        await asyncio.Event().wait()
                    finally:
                        raise cleanup

            with pytest.raises(ExceptionGroup) as caught:
                async with asyncio.TaskGroup() as group:
                    group.create_task(nested_failing_child())
                    group.create_task(sibling_with_cleanup_failure())

            runtime.execute_registered_stdlib("platform_name", [])
            return parent, caught.value

    parent, group = asyncio.run(scenario())
    leaves = _flatten(group)
    assert sum(error is first for error in leaves) == 1
    assert sum(error is cleanup for error in leaves) == 1
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)


def test_external_cancellation_with_cleanup_error_keeps_single_cleanup_leaf():
    cleanup = ArithmeticError("cleanup failed once")

    async def scenario():
        with runtime.runtime_execution_context(max_events=3) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            started = asyncio.Event()

            async def child():
                with runtime.runtime_execution_context(max_events=2):
                    runtime.execute_registered_stdlib("current_directory", [])
                    try:
                        started.set()
                        await asyncio.Event().wait()
                    finally:
                        raise cleanup

            async def grouped():
                async with asyncio.TaskGroup() as group:
                    group.create_task(child())
                    await asyncio.Event().wait()

            task = asyncio.create_task(grouped())
            await started.wait()
            task.cancel("external cancellation")
            with pytest.raises(BaseExceptionGroup) as caught:
                await task
            runtime.execute_registered_stdlib("platform_name", [])
            return parent, caught.value

    parent, group = asyncio.run(scenario())
    leaves = _flatten(group)
    assert sum(error is cleanup for error in leaves) == 1
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)
