from __future__ import annotations

import asyncio

import pytest

import slang.stdlib_runtime as runtime


def test_repeated_taskgroup_cancellation_during_nested_cleanup_restores_parent():
    async def scenario():
        with runtime.runtime_execution_context(max_events=4) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            child_entered = asyncio.Event()
            cleanup_started = asyncio.Event()
            child_task_holder: list[asyncio.Task] = []

            async def child():
                with runtime.runtime_execution_context(max_events=3):
                    runtime.execute_registered_stdlib("current_directory", [])
                    with runtime.runtime_execution_context(max_events=2):
                        runtime.execute_registered_stdlib("platform_name", [])
                        child_entered.set()
                        try:
                            await asyncio.Event().wait()
                        finally:
                            cleanup_started.set()
                            await asyncio.Event().wait()

            async def grouped_work():
                async with asyncio.TaskGroup() as group:
                    child_task_holder.append(group.create_task(child()))
                    await child_entered.wait()
                    await asyncio.Event().wait()

            task = asyncio.create_task(grouped_work())
            await child_entered.wait()
            task.cancel("first group cancellation")
            await cleanup_started.wait()
            child_task_holder[0].cancel("second child cancellation")
            with pytest.raises(asyncio.CancelledError) as caught:
                await task

            runtime.execute_registered_stdlib("platform_name", [])
            return parent, caught.value

    parent, cancellation = asyncio.run(scenario())
    assert str(cancellation) == "first group cancellation"
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)


def test_nested_taskgroups_unwind_all_contexts_after_outer_cancellation():
    async def scenario():
        with runtime.runtime_execution_context(max_events=5) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            deepest_entered = asyncio.Event()
            cleanup_levels: list[int] = []

            async def deepest():
                with runtime.runtime_execution_context(max_events=2):
                    runtime.execute_registered_stdlib("current_directory", [])
                    try:
                        deepest_entered.set()
                        await asyncio.Event().wait()
                    finally:
                        cleanup_levels.append(3)

            async def middle_group():
                with runtime.runtime_execution_context(max_events=3):
                    runtime.execute_registered_stdlib("platform_name", [])
                    async with asyncio.TaskGroup() as inner:
                        inner.create_task(deepest())
                        await deepest_entered.wait()
                        await asyncio.Event().wait()

            async def outer_group():
                with runtime.runtime_execution_context(max_events=4):
                    runtime.execute_registered_stdlib("current_directory", [])
                    async with asyncio.TaskGroup() as outer:
                        outer.create_task(middle_group())
                        await deepest_entered.wait()
                        await asyncio.Event().wait()

            task = asyncio.create_task(outer_group())
            await deepest_entered.wait()
            task.cancel("cancel nested groups")
            with pytest.raises(asyncio.CancelledError) as caught:
                await task
            runtime.execute_registered_stdlib("platform_name", [])
            return parent, caught.value, cleanup_levels

    parent, cancellation, cleanup_levels = asyncio.run(scenario())
    assert str(cancellation) == "cancel nested groups"
    assert cleanup_levels == [3]
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)


def test_external_taskgroup_cancellation_cleans_multiple_children_independently():
    async def scenario():
        with runtime.runtime_execution_context(max_events=5) as parent:
            runtime.execute_registered_stdlib("platform_name", [])
            ready = 0
            all_ready = asyncio.Event()
            cleanup: set[str] = set()

            async def child(name: str):
                nonlocal ready
                with runtime.runtime_execution_context(max_events=2):
                    runtime.execute_registered_stdlib("current_directory", [])
                    ready += 1
                    if ready == 2:
                        all_ready.set()
                    try:
                        await all_ready.wait()
                        await asyncio.Event().wait()
                    finally:
                        cleanup.add(name)

            async def group_work():
                async with asyncio.TaskGroup() as group:
                    group.create_task(child("first"))
                    group.create_task(child("second"))
                    await all_ready.wait()
                    await asyncio.Event().wait()

            task = asyncio.create_task(group_work())
            await all_ready.wait()
            task.cancel("cancel all children")
            with pytest.raises(asyncio.CancelledError) as caught:
                await task
            runtime.execute_registered_stdlib("platform_name", [])
            return parent, caught.value, cleanup

    parent, cancellation, cleanup = asyncio.run(scenario())
    assert str(cancellation) == "cancel all children"
    assert cleanup == {"first", "second"}
    assert parent.event_count == 2
    assert parent.summary.calls_by_name == (("platform_name", 2),)
    assert all(event.name == "platform_name" for event in parent.events)
