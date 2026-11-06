from __future__ import annotations

import asyncio

import pytest

import slang.stdlib_runtime as runtime


def _flatten_exception_group(group: BaseExceptionGroup) -> list[BaseException]:
    flattened: list[BaseException] = []
    for error in group.exceptions:
        if isinstance(error, BaseExceptionGroup):
            flattened.extend(_flatten_exception_group(error))
        else:
            flattened.append(error)
    return flattened


def test_taskgroup_keeps_original_failure_and_cleanup_failure_together():
    original = RuntimeError("original child failure")
    cleanup_error = LookupError("sibling cleanup failure")

    async def scenario():
        with runtime.runtime_execution_context(max_events=4) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            sibling_started = asyncio.Event()
            cleanup_started = asyncio.Event()

            async def failing_child():
                with runtime.runtime_execution_context(max_events=2):
                    runtime.execute_registered_stdlib("current_directory", [])
                    await sibling_started.wait()
                    raise original

            async def sibling_child():
                with runtime.runtime_execution_context(max_events=2):
                    runtime.execute_registered_stdlib("current_directory", [])
                    sibling_started.set()
                    try:
                        await asyncio.Event().wait()
                    finally:
                        cleanup_started.set()
                        raise cleanup_error

            with pytest.raises(BaseExceptionGroup) as caught:
                async with asyncio.TaskGroup() as group:
                    group.create_task(failing_child())
                    group.create_task(sibling_child())

            assert cleanup_started.is_set()
            runtime.execute_registered_stdlib("platform_name", [])
            return parent, caught.value

    parent, group_error = asyncio.run(scenario())
    leaves = _flatten_exception_group(group_error)
    assert any(error is original for error in leaves)
    assert any(error is cleanup_error for error in leaves)
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)


def test_multiple_cleanup_failures_are_preserved_after_group_cancellation():
    first_cleanup_error = ValueError("first cleanup failed")
    second_cleanup_error = OSError("second cleanup failed")

    async def scenario():
        with runtime.runtime_execution_context(max_events=4) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            ready = 0
            both_ready = asyncio.Event()

            async def child(name: str, cleanup_error: Exception):
                nonlocal ready
                with runtime.runtime_execution_context(max_events=2):
                    runtime.execute_registered_stdlib("current_directory", [])
                    ready += 1
                    if ready == 2:
                        both_ready.set()
                    try:
                        await both_ready.wait()
                        await asyncio.Event().wait()
                    finally:
                        raise cleanup_error

            task = asyncio.create_task(
                _run_group(child, first_cleanup_error, second_cleanup_error)
            )
            await both_ready.wait()
            task.cancel("external cancellation")
            with pytest.raises(BaseExceptionGroup) as caught:
                await task
            runtime.execute_registered_stdlib("platform_name", [])
            return parent, caught.value

    parent, group_error = asyncio.run(scenario())
    leaves = _flatten_exception_group(group_error)
    assert any(error is first_cleanup_error for error in leaves)
    assert any(error is second_cleanup_error for error in leaves)
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)


async def _run_group(child, first_cleanup_error: Exception, second_cleanup_error: Exception):
    async with asyncio.TaskGroup() as group:
        group.create_task(child("first", first_cleanup_error))
        group.create_task(child("second", second_cleanup_error))
        await asyncio.Event().wait()


def test_parent_budget_remains_usable_after_group_with_multiple_cleanup_errors():
    first_cleanup_error = ValueError("first cleanup failed")
    second_cleanup_error = RuntimeError("second cleanup failed")

    async def scenario():
        with runtime.runtime_execution_context(max_events=3) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            ready = 0
            both_ready = asyncio.Event()

            async def child(error: Exception):
                nonlocal ready
                with runtime.runtime_execution_context(max_events=2):
                    runtime.execute_registered_stdlib("current_directory", [])
                    ready += 1
                    if ready == 2:
                        both_ready.set()
                    try:
                        await both_ready.wait()
                        raise error
                    finally:
                        await asyncio.sleep(0)

            with pytest.raises(ExceptionGroup) as caught:
                async with asyncio.TaskGroup() as group:
                    group.create_task(child(first_cleanup_error))
                    group.create_task(child(second_cleanup_error))

            leaves = _flatten_exception_group(caught.value)
            assert any(error is first_cleanup_error for error in leaves)
            assert any(error is second_cleanup_error for error in leaves)
            runtime.execute_registered_stdlib("platform_name", [])
            return parent

    parent = asyncio.run(scenario())
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)
