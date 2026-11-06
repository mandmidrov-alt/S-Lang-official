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


def test_second_external_cancellation_during_nested_group_cleanup_preserves_failure():
    original = RuntimeError("nested original failure")
    cleanup_error = LookupError("nested cleanup failure")

    async def scenario():
        with runtime.runtime_execution_context(max_events=5) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            sibling_cleanup = asyncio.Event()
            release_cleanup = asyncio.Event()

            async def failing_leaf():
                with runtime.runtime_execution_context(max_events=2):
                    runtime.execute_registered_stdlib("current_directory", [])
                    await sibling_cleanup.wait()
                    raise original

            async def waiting_leaf():
                with runtime.runtime_execution_context(max_events=2):
                    runtime.execute_registered_stdlib("current_directory", [])
                    try:
                        sibling_cleanup.set()
                        await asyncio.Event().wait()
                    finally:
                        await release_cleanup.wait()
                        raise cleanup_error

            async def nested_group():
                async with asyncio.TaskGroup() as inner:
                    inner.create_task(failing_leaf())
                    inner.create_task(waiting_leaf())

            task = asyncio.create_task(nested_group())
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            task.cancel("external cancellation during cleanup")
            release_cleanup.set()
            with pytest.raises(BaseExceptionGroup) as caught:
                await task
            runtime.execute_registered_stdlib("platform_name", [])
            return parent, caught.value

    parent, error_group = asyncio.run(scenario())
    leaves = _flatten(error_group)
    assert sum(error is original for error in leaves) == 1
    assert sum(error is cleanup_error for error in leaves) == 1
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)


def test_nested_contexts_finalize_once_when_cancellation_repeats_in_finally():
    async def scenario():
        with runtime.runtime_execution_context(max_events=4) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            entered = asyncio.Event()
            cleanup_entered = asyncio.Event()
            finish_cleanup = asyncio.Event()

            async def child():
                with runtime.runtime_execution_context(max_events=3):
                    runtime.execute_registered_stdlib("current_directory", [])
                    with runtime.runtime_execution_context(max_events=2):
                        runtime.execute_registered_stdlib("platform_name", [])
                        try:
                            entered.set()
                            await asyncio.Event().wait()
                        finally:
                            cleanup_entered.set()
                            await finish_cleanup.wait()

            task = asyncio.create_task(child())
            await entered.wait()
            task.cancel("first cancellation")
            await cleanup_entered.wait()
            task.cancel("second cancellation")
            finish_cleanup.set()
            with pytest.raises(asyncio.CancelledError) as caught:
                await task
            runtime.execute_registered_stdlib("platform_name", [])
            return parent, caught.value

    parent, cancellation = asyncio.run(scenario())
    assert str(cancellation) == "second cancellation"
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)


def test_parent_context_remains_usable_after_nested_group_cleanup_errors():
    first = ValueError("first nested cleanup")
    second = OSError("second nested cleanup")

    async def scenario():
        with runtime.runtime_execution_context(max_events=4) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            ready = 0
            both_ready = asyncio.Event()

            async def child(error: Exception):
                nonlocal ready
                with runtime.runtime_execution_context(max_events=2):
                    runtime.execute_registered_stdlib("current_directory", [])
                    with runtime.runtime_execution_context(max_events=1):
                        runtime.execute_registered_stdlib("platform_name", [])
                        ready += 1
                        if ready == 2:
                            both_ready.set()
                        try:
                            await both_ready.wait()
                            await asyncio.Event().wait()
                        finally:
                            raise error

            task = asyncio.create_task(_run_group(child(first), child(second)))
            await both_ready.wait()
            task.cancel("cancel nested group")
            with pytest.raises(BaseExceptionGroup) as caught:
                await task
            runtime.execute_registered_stdlib("platform_name", [])
            return parent, caught.value

    parent, error_group = asyncio.run(scenario())
    leaves = _flatten(error_group)
    assert sum(error is first for error in leaves) == 1
    assert sum(error is second for error in leaves) == 1
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)


async def _run_group(first, second):
    async with asyncio.TaskGroup() as group:
        group.create_task(first)
        group.create_task(second)
        await asyncio.Event().wait()
