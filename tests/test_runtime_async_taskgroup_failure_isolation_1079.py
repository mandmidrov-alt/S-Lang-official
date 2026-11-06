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


def test_child_failure_cancels_sibling_without_sharing_cancellation_state():
    original = RuntimeError("child failed")

    async def scenario():
        with runtime.runtime_execution_context(max_events=4) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            sibling_started = asyncio.Event()
            sibling_cancelled = asyncio.Event()
            sibling_count: list[int] = []

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
                    except asyncio.CancelledError:
                        task = asyncio.current_task()
                        assert task is not None
                        sibling_count.append(task.cancelling())
                        sibling_cancelled.set()
                        raise

            with pytest.raises(ExceptionGroup) as caught:
                async with asyncio.TaskGroup() as group:
                    group.create_task(failing_child())
                    group.create_task(sibling_child())
            assert sibling_cancelled.is_set()
            runtime.execute_registered_stdlib("platform_name", [])
            return parent, caught.value, sibling_count

    parent, errors, sibling_count = asyncio.run(scenario())
    leaves = _flatten_exception_group(errors)
    assert sum(error is original for error in leaves) == 1
    assert sibling_count == [1]
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)


def test_sibling_cleanup_failure_is_preserved_once_when_other_child_fails():
    original = RuntimeError("primary child failure")
    cleanup_error = LookupError("sibling cleanup failure")

    async def scenario():
        with runtime.runtime_execution_context(max_events=4) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            ready = 0
            both_ready = asyncio.Event()
            cleanup_started = asyncio.Event()

            async def failing_child():
                nonlocal ready
                with runtime.runtime_execution_context(max_events=2):
                    runtime.execute_registered_stdlib("current_directory", [])
                    ready += 1
                    if ready == 2:
                        both_ready.set()
                    await both_ready.wait()
                    raise original

            async def cleanup_child():
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
                        cleanup_started.set()
                        raise cleanup_error

            with pytest.raises(ExceptionGroup) as caught:
                async with asyncio.TaskGroup() as group:
                    group.create_task(failing_child())
                    group.create_task(cleanup_child())
            assert cleanup_started.is_set()
            runtime.execute_registered_stdlib("platform_name", [])
            return parent, caught.value

    parent, errors = asyncio.run(scenario())
    leaves = _flatten_exception_group(errors)
    assert sum(error is original for error in leaves) == 1
    assert sum(error is cleanup_error for error in leaves) == 1
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)


def test_failed_group_does_not_corrupt_parent_budget_or_later_task_context():
    original = ValueError("isolated failure")

    async def scenario():
        with runtime.runtime_execution_context(max_events=3) as parent:
            runtime.execute_registered_stdlib("platform_name", [])

            async def failing_child():
                with runtime.runtime_execution_context(max_events=1):
                    runtime.execute_registered_stdlib("current_directory", [])
                    raise original

            with pytest.raises(ExceptionGroup) as caught:
                async with asyncio.TaskGroup() as group:
                    group.create_task(failing_child())

            runtime.execute_registered_stdlib("platform_name", [])
            async def later_child():
                with runtime.runtime_execution_context(max_events=1):
                    runtime.execute_registered_stdlib("current_directory", [])
                    return asyncio.current_task() is not None

            later_result = await asyncio.create_task(later_child())
            runtime.execute_registered_stdlib("platform_name", [])
            return parent, caught.value, later_result

    parent, errors, later_result = asyncio.run(scenario())
    leaves = _flatten_exception_group(errors)
    assert sum(error is original for error in leaves) == 1
    assert later_result is True
    assert parent.event_count == 3
    assert parent.summary.calls_by_name == (("platform_name", 3),)
    assert all(event.name == "platform_name" for event in parent.events)
