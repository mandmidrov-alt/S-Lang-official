from __future__ import annotations

import asyncio

import pytest

import slang.stdlib_runtime as runtime


def test_cancelled_child_restores_parent_budget_and_trace():
    async def scenario():
        with runtime.runtime_execution_context(max_events=3) as parent:
            runtime.execute_registered_stdlib("platform_name", [])

            entered = asyncio.Event()

            async def child():
                with runtime.runtime_execution_context(max_events=2) as child_context:
                    runtime.execute_registered_stdlib("current_directory", [])
                    entered.set()
                    await asyncio.Event().wait()
                return child_context

            task = asyncio.create_task(child())
            await entered.wait()
            task.cancel("cancel nested execution")
            with pytest.raises(asyncio.CancelledError) as caught:
                await task
            runtime.execute_registered_stdlib("platform_name", [])
            return parent, caught.value

    parent, cancellation = asyncio.run(scenario())
    assert str(cancellation) == "cancel nested execution"
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name != "current_directory" for event in parent.events)


def test_cancelled_child_preserves_parent_limit_counter():
    async def scenario():
        with runtime.runtime_execution_context(max_events=2) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            entered = asyncio.Event()

            async def child():
                with runtime.runtime_execution_context(max_events=10):
                    runtime.execute_registered_stdlib("current_directory", [])
                    entered.set()
                    await asyncio.Event().wait()

            task = asyncio.create_task(child())
            await entered.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            runtime.execute_registered_stdlib("platform_name", [])
            with pytest.raises(runtime.RuntimeLimitError, match="event limit"):
                runtime.execute_registered_stdlib("platform_name", [])
            return parent

    parent = asyncio.run(scenario())
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)


def test_child_context_cleanup_runs_when_non_cancellation_error_occurs():
    original = ValueError("child failure")

    async def scenario():
        with runtime.runtime_execution_context(max_events=3) as parent:
            runtime.execute_registered_stdlib("platform_name", [])

            async def child():
                with runtime.runtime_execution_context(max_events=2):
                    runtime.execute_registered_stdlib("current_directory", [])
                    raise original

            with pytest.raises(ValueError) as caught:
                await asyncio.create_task(child())
            assert caught.value is original
            runtime.execute_registered_stdlib("platform_name", [])
            return parent

    parent = asyncio.run(scenario())
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
