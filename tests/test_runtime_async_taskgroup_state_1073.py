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


def test_taskgroup_preserves_original_failure_when_sibling_is_cancelled_during_cleanup():
    original = RuntimeError("original child failure")

    async def scenario():
        with runtime.runtime_execution_context(max_events=4) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            sibling_started = asyncio.Event()
            cleanup_started = asyncio.Event()
            release_cleanup = asyncio.Event()

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
                        await release_cleanup.wait()

            async def run_group():
                async with asyncio.TaskGroup() as group:
                    group.create_task(failing_child())
                    group.create_task(sibling_child())

            task = asyncio.create_task(run_group())
            await cleanup_started.wait()
            # TaskGroup's failure cancellation has already interrupted the sibling;
            # a second external cancellation exercises cleanup under cancellation pressure.
            task.cancel("second cancellation during cleanup")
            release_cleanup.set()
            with pytest.raises(BaseExceptionGroup) as caught:
                await task
            runtime.execute_registered_stdlib("platform_name", [])
            return parent, caught.value

    parent, error_group = asyncio.run(scenario())
    leaves = _flatten_exception_group(error_group)
    assert any(error is original for error in leaves)
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)


def test_cancelled_error_in_finally_does_not_leave_nested_context_state_active():
    async def scenario():
        with runtime.runtime_execution_context(max_events=4) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            child_entered = asyncio.Event()
            entered_cleanup = asyncio.Event()
            allow_cleanup = asyncio.Event()

            async def child():
                with runtime.runtime_execution_context(max_events=2):
                    runtime.execute_registered_stdlib("current_directory", [])
                    with runtime.runtime_execution_context(max_events=1):
                        runtime.execute_registered_stdlib("platform_name", [])
                        try:
                            child_entered.set()
                            await asyncio.Event().wait()
                        finally:
                            entered_cleanup.set()
                            await allow_cleanup.wait()

            task = asyncio.create_task(child())
            await child_entered.wait()
            task.cancel("first cancellation")
            await entered_cleanup.wait()
            task.cancel("second cancellation in finally")
            allow_cleanup.set()
            with pytest.raises(asyncio.CancelledError) as caught:
                await task
            runtime.execute_registered_stdlib("platform_name", [])
            return parent, caught.value

    parent, cancellation = asyncio.run(scenario())
    assert str(cancellation) == "second cancellation in finally"
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)


def test_sequential_nested_cancellations_restore_parent_event_budget():
    async def scenario():
        with runtime.runtime_execution_context(max_events=3) as parent:
            runtime.execute_registered_stdlib("platform_name", [])

            async def cancelled_child(name: str, entered: asyncio.Event):
                with runtime.runtime_execution_context(max_events=2):
                    runtime.execute_registered_stdlib("current_directory", [])
                    with runtime.runtime_execution_context(max_events=1):
                        runtime.execute_registered_stdlib("platform_name", [])
                        entered.set()
                        await asyncio.Event().wait()

            for name in ("first", "second"):
                entered = asyncio.Event()
                task = asyncio.create_task(cancelled_child(name, entered))
                await entered.wait()
                task.cancel(name)
                with pytest.raises(asyncio.CancelledError):
                    await task
                runtime.execute_registered_stdlib("platform_name", [])

            return parent

    parent = asyncio.run(scenario())
    assert parent.event_count == 3
    assert parent.summary.calls_by_name == (("platform_name", 3),)
    assert all(event.name == "platform_name" for event in parent.events)
