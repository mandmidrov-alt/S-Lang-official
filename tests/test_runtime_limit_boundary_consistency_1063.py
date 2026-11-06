from __future__ import annotations

import time

import pytest

from slang.stdlib_runtime import (
    RuntimeLimitError,
    execute_registered_stdlib,
    execute_runtime_call,
    runtime_execution_context,
)


def test_registered_call_that_exceeds_duration_is_traced_as_failed():
    with runtime_execution_context(max_duration_ms=1) as context:
        with pytest.raises(RuntimeLimitError, match="duration limit"):
            execute_registered_stdlib("sleep_seconds", [0.02])

    assert context.event_count == 1
    event = context.events[0]
    assert event.name == "sleep_seconds"
    assert event.success is False
    assert event.error_type == "RuntimeLimitError"
    assert event.duration_ms >= 1


def test_catalog_compatibility_call_that_exceeds_duration_is_traced_as_failed():
    def slow_evaluator(_args):
        time.sleep(0.02)
        return "finished"

    with runtime_execution_context(max_duration_ms=1) as context:
        with pytest.raises(RuntimeLimitError, match="duration limit"):
            execute_runtime_call("read_text", ["unused.txt"], slow_evaluator)

    assert context.event_count == 1
    event = context.events[0]
    assert event.name == "read_text"
    assert event.success is False
    assert event.error_type == "RuntimeLimitError"
    assert event.duration_ms >= 1


def test_short_registered_call_still_succeeds_with_duration_budget():
    with runtime_execution_context(max_duration_ms=1000) as context:
        handled, result = execute_registered_stdlib("platform_name", [])

    assert handled is True
    assert isinstance(result, str)
    assert context.event_count == 1
    assert context.events[0].success is True
