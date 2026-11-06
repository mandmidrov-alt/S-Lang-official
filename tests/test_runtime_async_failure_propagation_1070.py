from __future__ import annotations

import asyncio

import pytest

import slang.stdlib_runtime as runtime


def test_gather_preserves_each_child_failure_and_keeps_trace_reports_separate():
    first_error = ValueError("first child failed")
    second_error = LookupError("second child failed")

    async def scenario():
        with runtime.runtime_execution_context(max_events=4) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            ready = 0
            both_ready = asyncio.Event()

            async def child(name, error):
                nonlocal ready
                with runtime.runtime_execution_context(max_events=3) as child_context:
                    runtime.execute_registered_stdlib(name, [])
                    ready += 1
                    if ready == 2:
                        both_ready.set()
                    await both_ready.wait()
                    raise error
                return child_context

            results = await asyncio.gather(
                child("current_directory", first_error),
                child("platform_name", second_error),
                return_exceptions=True,
            )
            runtime.execute_registered_stdlib("platform_name", [])
            return parent, results

    parent, results = asyncio.run(scenario())
    assert results[0] is first_error
    assert results[1] is second_error
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)


def test_child_failure_propagates_unchanged_through_nested_contexts():
    original = RuntimeError("failure at deepest level")

    async def scenario():
        with runtime.runtime_execution_context(max_events=4) as parent:
            runtime.execute_registered_stdlib("platform_name", [])

            async def child():
                with runtime.runtime_execution_context(max_events=3):
                    runtime.execute_registered_stdlib("current_directory", [])
                    with runtime.runtime_execution_context(max_events=2):
                        runtime.execute_registered_stdlib("platform_name", [])
                        raise original

            with pytest.raises(RuntimeError) as caught:
                await asyncio.create_task(child())
            runtime.execute_registered_stdlib("platform_name", [])
            return parent, caught.value

    parent, propagated = asyncio.run(scenario())
    assert propagated is original
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)


def test_one_failed_child_does_not_change_sibling_or_parent_context():
    original = ValueError("isolated child error")

    async def scenario():
        with runtime.runtime_execution_context(max_events=4) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            sibling_ready = asyncio.Event()

            async def failing_child():
                with runtime.runtime_execution_context(max_events=2):
                    runtime.execute_registered_stdlib("current_directory", [])
                    raise original

            async def successful_child():
                with runtime.runtime_execution_context(max_events=2) as own_context:
                    runtime.execute_registered_stdlib("platform_name", [])
                    sibling_ready.set()
                    await sibling_ready.wait()
                    return own_context.summary.calls_by_name

            failed, successful = await asyncio.gather(
                failing_child(), successful_child(), return_exceptions=True
            )
            runtime.execute_registered_stdlib("platform_name", [])
            return parent, failed, successful

    parent, failed, successful = asyncio.run(scenario())
    assert failed is original
    assert successful == (("platform_name", 1),)
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)
