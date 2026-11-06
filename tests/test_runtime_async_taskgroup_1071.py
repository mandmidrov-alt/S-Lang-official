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


def test_taskgroup_preserves_simultaneous_child_failures_and_parent_trace():
    first_error = ValueError("first task failed")
    second_error = LookupError("second task failed")

    async def scenario():
        with runtime.runtime_execution_context(max_events=4) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            ready = 0
            both_ready = asyncio.Event()

            async def child(name: str, error: Exception):
                nonlocal ready
                with runtime.runtime_execution_context(max_events=2):
                    runtime.execute_registered_stdlib(name, [])
                    ready += 1
                    if ready == 2:
                        both_ready.set()
                    await both_ready.wait()
                    raise error

            with pytest.raises(ExceptionGroup) as caught:
                async with asyncio.TaskGroup() as group:
                    group.create_task(child("current_directory", first_error))
                    group.create_task(child("platform_name", second_error))

            runtime.execute_registered_stdlib("platform_name", [])
            return parent, caught.value

    parent, group_error = asyncio.run(scenario())
    leaves = _flatten_exception_group(group_error)
    assert len(leaves) == 2
    assert any(error is first_error for error in leaves)
    assert any(error is second_error for error in leaves)
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)


def test_taskgroup_failure_cancels_sibling_and_unwinds_its_nested_context():
    original = RuntimeError("task group failure")

    async def scenario():
        with runtime.runtime_execution_context(max_events=4) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            sibling_started = asyncio.Event()
            sibling_cleanup = asyncio.Event()

            async def failing_child():
                with runtime.runtime_execution_context(max_events=2):
                    runtime.execute_registered_stdlib("current_directory", [])
                    await sibling_started.wait()
                    raise original

            async def sibling_child():
                with runtime.runtime_execution_context(max_events=3):
                    runtime.execute_registered_stdlib("current_directory", [])
                    with runtime.runtime_execution_context(max_events=2):
                        runtime.execute_registered_stdlib("platform_name", [])
                        sibling_started.set()
                        try:
                            await asyncio.Event().wait()
                        finally:
                            sibling_cleanup.set()

            with pytest.raises(ExceptionGroup) as caught:
                async with asyncio.TaskGroup() as group:
                    group.create_task(failing_child())
                    group.create_task(sibling_child())

            runtime.execute_registered_stdlib("platform_name", [])
            return parent, caught.value, sibling_cleanup.is_set()

    parent, group_error, cleanup_ran = asyncio.run(scenario())
    assert _flatten_exception_group(group_error) == [original]
    assert cleanup_ran
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)


def test_external_cancellation_of_taskgroup_restores_parent_execution_context():
    async def scenario():
        with runtime.runtime_execution_context(max_events=3) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            child_entered = asyncio.Event()

            async def child():
                with runtime.runtime_execution_context(max_events=2):
                    runtime.execute_registered_stdlib("current_directory", [])
                    with runtime.runtime_execution_context(max_events=1):
                        runtime.execute_registered_stdlib("platform_name", [])
                        child_entered.set()
                        await asyncio.Event().wait()

            async def parent_task():
                async with asyncio.TaskGroup() as group:
                    group.create_task(child())
                    await child_entered.wait()
                    await asyncio.Event().wait()

            task = asyncio.create_task(parent_task())
            await child_entered.wait()
            task.cancel("cancel task group")
            with pytest.raises(asyncio.CancelledError) as caught:
                await task

            runtime.execute_registered_stdlib("platform_name", [])
            return parent, caught.value

    parent, cancellation = asyncio.run(scenario())
    assert str(cancellation) == "cancel task group"
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)
