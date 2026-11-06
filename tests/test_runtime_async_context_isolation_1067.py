import asyncio

import pytest

from slang.stdlib_runtime import RuntimeLimitError, execute_registered_stdlib, runtime_execution_context


async def _run_task(label: str, calls: int):
    with runtime_execution_context(max_events=1) as context:
        execute_registered_stdlib("platform_name", [])
        if calls > 1:
            with pytest.raises(RuntimeLimitError):
                execute_registered_stdlib("current_directory", [])
        await asyncio.sleep(0)
        return label, context.event_count, context.summary.calls_by_name


def test_parallel_tasks_keep_separate_runtime_budgets_and_traces():
    async def scenario():
        return await asyncio.gather(
            _run_task("one", 1),
            _run_task("two", 2),
            _run_task("three", 1),
        )

    results = asyncio.run(scenario())
    by_label = {label: (count, calls) for label, count, calls in results}
    assert by_label == {
        "one": (1, (("platform_name", 1),)),
        "two": (1, (("platform_name", 1),)),
        "three": (1, (("platform_name", 1),)),
    }


def test_nested_async_runtime_context_restores_parent_state():
    async def scenario():
        with runtime_execution_context(max_events=3) as outer:
            execute_registered_stdlib("platform_name", [])

            async def child():
                with runtime_execution_context(max_events=1) as inner:
                    execute_registered_stdlib("current_directory", [])
                    await asyncio.sleep(0)
                    return inner.event_count, inner.summary.calls_by_name

            child_result = await asyncio.create_task(child())
            execute_registered_stdlib("platform_name", [])
            return outer.event_count, outer.summary.calls_by_name, child_result

    outer_count, outer_calls, child_result = asyncio.run(scenario())
    assert outer_count == 2
    assert outer_calls == (("platform_name", 2),)
    assert child_result == (1, (("current_directory", 1),))
