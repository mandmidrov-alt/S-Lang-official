from __future__ import annotations

import asyncio

import pytest

import slang.stdlib_runtime as runtime


def test_parallel_tasks_keep_independent_cancellation_counts():
    async def scenario():
        entered_a = asyncio.Event()
        entered_b = asyncio.Event()
        cleanup_a = asyncio.Event()
        cleanup_b = asyncio.Event()
        release_a = asyncio.Event()
        release_b = asyncio.Event()
        observed: dict[str, int] = {}

        async def worker(name, entered, cleanup, release):
            try:
                entered.set()
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cleanup.set()
                try:
                    await release.wait()
                except asyncio.CancelledError:
                    current = asyncio.current_task()
                    assert current is not None
                    observed[name] = current.cancelling()
                    # Suppress only the second cancellation so the counter can be inspected.
                    current.uncancel()
                    return
                current = asyncio.current_task()
                assert current is not None
                observed[name] = current.cancelling()
                return

        task_a = asyncio.create_task(worker("a", entered_a, cleanup_a, release_a))
        task_b = asyncio.create_task(worker("b", entered_b, cleanup_b, release_b))
        await entered_a.wait()
        await entered_b.wait()
        task_a.cancel("a-first")
        task_b.cancel("b-first")
        await cleanup_a.wait()
        await cleanup_b.wait()
        task_a.cancel("a-second")
        release_a.set()
        release_b.set()
        await asyncio.gather(task_a, task_b)
        return observed, task_a.cancelling(), task_b.cancelling()

    observed, count_a, count_b = asyncio.run(scenario())
    assert observed == {"a": 2, "b": 1}
    assert count_a == 1  # one cancellation remains after explicitly consuming the second
    assert count_b == 1


def test_uncancel_in_one_concurrent_task_does_not_change_sibling_count():
    async def scenario():
        ready = asyncio.Event()
        sibling_ready = asyncio.Event()
        finish = asyncio.Event()
        results: dict[str, tuple[int, int]] = {}

        async def recovering_worker():
            try:
                ready.set()
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                current = asyncio.current_task()
                assert current is not None
                before = current.cancelling()
                after = current.uncancel()
                results["recovering"] = (before, after)
                await finish.wait()

        async def sibling_worker():
            try:
                sibling_ready.set()
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                current = asyncio.current_task()
                assert current is not None
                results["sibling"] = (current.cancelling(), current.cancelling())
                await finish.wait()

        recovering = asyncio.create_task(recovering_worker())
        sibling = asyncio.create_task(sibling_worker())
        await ready.wait()
        await sibling_ready.wait()
        recovering.cancel("recover this task")
        sibling.cancel("leave sibling count intact")
        await asyncio.sleep(0)
        finish.set()
        await asyncio.gather(recovering, sibling)
        return results, recovering.cancelling(), sibling.cancelling()

    results, recovering_count, sibling_count = asyncio.run(scenario())
    assert results == {"recovering": (1, 0), "sibling": (1, 1)}
    assert recovering_count == 0
    assert sibling_count == 1


def test_concurrent_cancellation_keeps_execution_context_reports_isolated():
    async def scenario():
        with runtime.runtime_execution_context(max_events=5) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            entered_a = asyncio.Event()
            entered_b = asyncio.Event()
            cleanup_a = asyncio.Event()
            cleanup_b = asyncio.Event()
            release = asyncio.Event()

            async def child(entered, cleanup, operation):
                with runtime.runtime_execution_context(max_events=3):
                    runtime.execute_registered_stdlib(operation, [])
                    try:
                        entered.set()
                        await asyncio.Event().wait()
                    finally:
                        cleanup.set()
                        await release.wait()

            task_a = asyncio.create_task(child(entered_a, cleanup_a, "current_directory"))
            task_b = asyncio.create_task(child(entered_b, cleanup_b, "platform_name"))
            await entered_a.wait()
            await entered_b.wait()
            task_a.cancel("cancel a")
            task_b.cancel("cancel b")
            await cleanup_a.wait()
            await cleanup_b.wait()
            release.set()
            outcomes = await asyncio.gather(task_a, task_b, return_exceptions=True)
            runtime.execute_registered_stdlib("platform_name", [])
            return parent, outcomes

    parent, outcomes = asyncio.run(scenario())
    assert all(isinstance(outcome, asyncio.CancelledError) for outcome in outcomes)
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)
