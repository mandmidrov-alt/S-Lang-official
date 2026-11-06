from __future__ import annotations

import pytest

from slang.stdlib_runtime import RuntimeLimitError, capture_runtime_trace, runtime_limits, execute_registered_stdlib


def test_event_limit_is_enforced_without_trace_sink():
    with runtime_limits(max_events=1):
        assert execute_registered_stdlib("platform_name", [])[0] is True
        with pytest.raises(RuntimeLimitError, match="event limit"):
            execute_registered_stdlib("platform_name", [])


def test_event_limit_counts_failed_calls():
    with capture_runtime_trace() as events:
        with runtime_limits(max_events=1):
            with pytest.raises(RuntimeError):
                execute_registered_stdlib("parse_datetime", ["not-a-date", ""])
            with pytest.raises(RuntimeLimitError):
                execute_registered_stdlib("platform_name", [])
    assert len(events) == 1
    assert events[0].success is False


def test_limits_are_context_local_and_restored():
    with runtime_limits(max_events=1):
        assert execute_registered_stdlib("platform_name", [])[0] is True
        with runtime_limits(max_events=2):
            assert execute_registered_stdlib("platform_name", [])[0] is True
            assert execute_registered_stdlib("platform_name", [])[0] is True
        with pytest.raises(RuntimeLimitError):
            execute_registered_stdlib("platform_name", [])
