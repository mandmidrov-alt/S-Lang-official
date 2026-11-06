from __future__ import annotations

from types import SimpleNamespace

import pytest

import slang.stdlib_runtime as runtime


def _raise_lookup_error(_args):
    raise LookupError("unexpected evaluator failure")


def test_registered_unexpected_failure_is_traced_and_consumes_event(monkeypatch):
    fake = SimpleNamespace(parameters=(), effect="PURE", evaluator=_raise_lookup_error)
    monkeypatch.setattr(runtime, "get_stdlib_function", lambda _name: fake)

    with runtime.runtime_execution_context(max_events=1) as context:
        with pytest.raises(LookupError, match="unexpected evaluator failure"):
            runtime.execute_registered_stdlib("test_unexpected", [])
        with pytest.raises(runtime.RuntimeLimitError, match="event limit"):
            runtime.execute_registered_stdlib("test_unexpected", [])

    assert context.event_count == 1
    assert context.events[0].success is False
    assert context.events[0].error_type == "LookupError"


def test_catalog_boundary_unexpected_failure_is_traced_and_consumes_event():
    with runtime.runtime_execution_context(max_events=1) as context:
        with pytest.raises(LookupError, match="unexpected evaluator failure"):
            runtime.execute_runtime_call("read_text", ["unused.txt"], _raise_lookup_error)
        with pytest.raises(runtime.RuntimeLimitError, match="event limit"):
            runtime.execute_runtime_call("read_text", ["unused.txt"], lambda _args: "ok")

    assert context.event_count == 1
    assert context.events[0].success is False
    assert context.events[0].error_type == "LookupError"


def test_nested_limit_context_restores_outer_event_budget():
    with runtime.runtime_execution_context(max_events=2) as outer:
        runtime.execute_registered_stdlib("platform_name", [])
        with runtime.runtime_execution_context(max_events=1) as inner:
            runtime.execute_registered_stdlib("platform_name", [])
            assert inner.event_count == 1
        # The inner context's event is isolated; the outer context retains its
        # own trace and one remaining event from its own budget.
        runtime.execute_registered_stdlib("platform_name", [])
        assert outer.event_count == 2

    assert outer.summary.event_count == 2
    assert inner.summary.event_count == 1
