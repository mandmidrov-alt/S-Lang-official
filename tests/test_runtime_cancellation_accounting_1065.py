from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import slang.stdlib_runtime as runtime


@pytest.mark.parametrize("exception_type", [asyncio.CancelledError, KeyboardInterrupt, SystemExit])
def test_registered_boundary_records_and_reraises_control_exceptions(monkeypatch, exception_type):
    original = exception_type("stop now")
    def interrupted(_args):
        raise original

    fake = SimpleNamespace(parameters=(), effect="PURE", evaluator=interrupted)
    monkeypatch.setattr(runtime, "get_stdlib_function", lambda _name: fake)

    with runtime.runtime_execution_context(max_events=1) as context:
        with pytest.raises(exception_type) as caught:
            runtime.execute_registered_stdlib("test_control", [])
        assert caught.value is original
        with pytest.raises(runtime.RuntimeLimitError, match="event limit"):
            runtime.execute_registered_stdlib("test_control", [])

    assert context.event_count == 1
    assert context.events[0].success is False
    assert context.events[0].error_type == exception_type.__name__


@pytest.mark.parametrize("exception_type", [asyncio.CancelledError, KeyboardInterrupt, SystemExit])
def test_catalog_boundary_records_and_reraises_control_exceptions(monkeypatch, exception_type):
    original = exception_type("stop now")
    def interrupted(_args):
        raise original

    monkeypatch.setattr(runtime, "runtime_call_metadata", lambda _name: ("IO", "filesystem"))

    with runtime.runtime_execution_context(max_events=1) as context:
        with pytest.raises(exception_type) as caught:
            runtime.execute_runtime_call("read_text", ["unused.txt"], interrupted)
        assert caught.value is original
        with pytest.raises(runtime.RuntimeLimitError, match="event limit"):
            runtime.execute_runtime_call("read_text", ["unused.txt"], lambda _args: "ok")

    assert context.event_count == 1
    assert context.events[0].success is False
    assert context.events[0].error_type == exception_type.__name__
