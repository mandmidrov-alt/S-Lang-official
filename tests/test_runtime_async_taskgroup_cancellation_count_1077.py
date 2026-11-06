from __future__ import annotations

import asyncio

import pytest

import slang.stdlib_runtime as runtime


def test_repeated_cancellation_count_and_uncancel_are_observable_during_cleanup():
    async def scenario():
        entered = asyncio.Event()
        cleanup_entered = asyncio.Event()
        release_cleanup = asyncio.Event()
        observed: list[int] = []
        uncancel_results: list[int] = []
        task: asyncio.Task | None = None

        async def worker():
            try:
                entered.set()
                await asyncio.Event().wait()
            finally:
                cleanup_entered.set()
                try:
                    await release_cleanup.wait()
                except asyncio.CancelledError:
                    assert task is not None
                    observed.append(task.cancelling())
                    uncancel_results.append(task.uncancel())
                    uncancel_results.append(task.uncancel())

        task = asyncio.create_task(worker())
        await entered.wait()
        task.cancel("first cancellation")
        await cleanup_entered.wait()
        assert task.cancelling() == 1
        task.cancel("second cancellation")
        release_cleanup.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        return observed, uncancel_results, task.cancelling()

    observed, uncancel_results, final_count = asyncio.run(scenario())
    assert observed == [2]
    assert uncancel_results == [1, 0]
    # The original cancellation still propagates, although the counter was explicitly cleared.
    assert final_count == 0


def test_nested_taskgroup_cancellation_does_not_corrupt_parent_context():
    async def scenario():
        with runtime.runtime_execution_context(max_events=5) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            child_entered = asyncio.Event()
            cleanup_entered = asyncio.Event()
            release_cleanup = asyncio.Event()
            child_counts: list[int] = []
            child_task: asyncio.Task | None = None

            async def child():
                with runtime.runtime_execution_context(max_events=2):
                    runtime.execute_registered_stdlib("current_directory", [])
                    with runtime.runtime_execution_context(max_events=1):
                        runtime.execute_registered_stdlib("platform_name", [])
                        child_entered.set()
                        try:
                            await asyncio.Event().wait()
                        finally:
                            cleanup_entered.set()
                            try:
                                await release_cleanup.wait()
                            except asyncio.CancelledError:
                                current = asyncio.current_task()
                                assert current is not None
                                child_counts.append(current.cancelling())
                                raise

            async def group_runner():
                nonlocal child_task
                async with asyncio.TaskGroup() as group:
                    child_task = group.create_task(child())
                    await child_entered.wait()
                    await asyncio.Event().wait()

            task = asyncio.create_task(group_runner())
            await child_entered.wait()
            assert child_task is not None
            child_task.cancel("first external cancellation")
            await cleanup_entered.wait()
            child_task.cancel("second external cancellation")
            release_cleanup.set()
            with pytest.raises(asyncio.CancelledError):
                await child_task
            task.cancel("stop group runner")
            with pytest.raises(asyncio.CancelledError):
                await task
            runtime.execute_registered_stdlib("platform_name", [])
            return parent, child_counts

    parent, child_counts = asyncio.run(scenario())
    assert child_counts == [2]
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)


def test_uncancelled_child_does_not_consume_parent_cancellation_or_event_budget():
    async def scenario():
        with runtime.runtime_execution_context(max_events=4) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            entered = asyncio.Event()
            cleanup = asyncio.Event()
            recovered: list[tuple[int, int]] = []

            async def child():
                with runtime.runtime_execution_context(max_events=2):
                    runtime.execute_registered_stdlib("current_directory", [])
                    try:
                        entered.set()
                        await asyncio.Event().wait()
                    except asyncio.CancelledError:
                        current = asyncio.current_task()
                        assert current is not None
                        before = current.cancelling()
                        after = current.uncancel()
                        recovered.append((before, after))
                        cleanup.set()
                        # Explicitly recover from this cancellation for this test.
                        return

            task = asyncio.create_task(child())
            await entered.wait()
            task.cancel("recoverable cancellation")
            await cleanup.wait()
            await task
            runtime.execute_registered_stdlib("platform_name", [])
            return parent, recovered, task.cancelling()

    parent, recovered, final_count = asyncio.run(scenario())
    assert recovered == [(1, 0)]
    assert final_count == 0
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)
