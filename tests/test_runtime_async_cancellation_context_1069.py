from __future__ import annotations

import asyncio

import pytest

import slang.stdlib_runtime as runtime


def test_repeated_cancellation_during_async_cleanup_restores_parent_context():
    async def scenario():
        with runtime.runtime_execution_context(max_events=4) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            started = asyncio.Event()
            cleanup_started = asyncio.Event()
            cleanup_gate = asyncio.Event()

            async def child():
                with runtime.runtime_execution_context(max_events=8):
                    runtime.execute_registered_stdlib("current_directory", [])
                    started.set()
                    try:
                        await asyncio.Event().wait()
                    finally:
                        cleanup_started.set()
                        await cleanup_gate.wait()

            task = asyncio.create_task(child())
            await started.wait()
            task.cancel("first cancellation")
            await cleanup_started.wait()
            task.cancel("second cancellation")
            with pytest.raises(asyncio.CancelledError) as caught:
                await task
            runtime.execute_registered_stdlib("platform_name", [])
            return parent, caught.value

    parent, cancellation = asyncio.run(scenario())
    assert str(cancellation) == "second cancellation"
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name != "current_directory" for event in parent.events)


def test_cancellation_unwinds_multiple_nested_execution_contexts():
    async def scenario():
        with runtime.runtime_execution_context(max_events=5) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            entered = asyncio.Event()

            async def child():
                with runtime.runtime_execution_context(max_events=4):
                    runtime.execute_registered_stdlib("current_directory", [])
                    with runtime.runtime_execution_context(max_events=3):
                        runtime.execute_registered_stdlib("platform_name", [])
                        entered.set()
                        await asyncio.Event().wait()

            task = asyncio.create_task(child())
            await entered.wait()
            task.cancel("unwind nested contexts")
            with pytest.raises(asyncio.CancelledError) as caught:
                await task
            runtime.execute_registered_stdlib("platform_name", [])
            return parent, caught.value

    parent, cancellation = asyncio.run(scenario())
    assert str(cancellation) == "unwind nested contexts"
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name not in {"current_directory"} for event in parent.events)


def test_cancelled_child_does_not_leave_context_values_in_reused_parent_task():
    async def scenario():
        with runtime.runtime_execution_context(max_events=3) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            child_ready = asyncio.Event()

            async def child():
                with runtime.runtime_execution_context(max_events=1):
                    runtime.execute_registered_stdlib("current_directory", [])
                    child_ready.set()
                    await asyncio.Event().wait()

            task = asyncio.create_task(child())
            await child_ready.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            runtime.execute_registered_stdlib("platform_name", [])
            return parent

    parent = asyncio.run(scenario())
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)
