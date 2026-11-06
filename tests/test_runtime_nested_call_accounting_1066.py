from types import SimpleNamespace

import pytest

import slang.stdlib_runtime as runtime


def test_nested_registered_calls_are_counted_before_evaluator_returns(monkeypatch):
    registry = {}

    def outer(_args):
        ok, value = runtime.execute_registered_stdlib("inner", [])
        assert ok
        return value + 1

    def inner(_args):
        return 41

    registry["outer"] = SimpleNamespace(parameters=(), effect="PURE", evaluator=outer)
    registry["inner"] = SimpleNamespace(parameters=(), effect="PURE", evaluator=inner)
    monkeypatch.setattr(runtime, "get_stdlib_function", lambda name: registry.get(name))

    with runtime.runtime_execution_context(max_events=2) as context:
        ok, value = runtime.execute_registered_stdlib("outer", [])

    assert ok and value == 42
    assert context.event_count == 2
    assert context.summary.successful_count == 2
    assert context.summary.calls_by_name == (("inner", 1), ("outer", 1))


def test_nested_calls_cannot_exceed_event_budget(monkeypatch):
    registry = {}

    def outer(_args):
        return runtime.execute_registered_stdlib("inner", [])[1]

    def inner(_args):
        return runtime.execute_registered_stdlib("leaf", [])[1]

    registry["outer"] = SimpleNamespace(parameters=(), effect="PURE", evaluator=outer)
    registry["inner"] = SimpleNamespace(parameters=(), effect="PURE", evaluator=inner)
    registry["leaf"] = SimpleNamespace(parameters=(), effect="PURE", evaluator=lambda _args: 7)
    monkeypatch.setattr(runtime, "get_stdlib_function", lambda name: registry.get(name))

    with runtime.runtime_execution_context(max_events=2) as context:
        with pytest.raises(runtime.RuntimeLimitError, match="event limit"):
            runtime.execute_registered_stdlib("outer", [])

    assert context.event_count == 2
    assert context.summary.failed_count == 2
    assert context.summary.calls_by_name == (("inner", 1), ("outer", 1))
    assert all(event.error_type == "RuntimeLimitError" for event in context.events)


def test_compatibility_boundary_and_registered_nested_calls_share_budget(monkeypatch):
    monkeypatch.setattr(runtime, "runtime_call_metadata", lambda name: ("PURE", "pure") if name == "legacy_outer" else None)
    monkeypatch.setattr(
        runtime,
        "get_stdlib_function",
        lambda name: SimpleNamespace(parameters=(), effect="PURE", evaluator=lambda _args: 9)
        if name == "registered_inner" else None,
    )

    with runtime.runtime_execution_context(max_events=1) as context:
        with pytest.raises(runtime.RuntimeLimitError, match="event limit"):
            runtime.execute_runtime_call(
                "legacy_outer", [],
                lambda _args: runtime.execute_registered_stdlib("registered_inner", []),
            )

    assert context.event_count == 1
    assert context.summary.calls_by_name == (("legacy_outer", 1),)
    assert context.summary.failed_count == 1
