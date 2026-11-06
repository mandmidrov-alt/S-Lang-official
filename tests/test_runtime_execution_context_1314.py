from slang.core import parse, runtime_execute
from slang.core import parse
from slang.stdlib_runtime import RuntimeLimitError


def _program(source: str):
    return parse(source)


def test_full_runtime_entrypoint_enforces_event_limit():
    p = _program('let x = now_utc()')
    try:
        runtime_execute(p, max_events=0)
    except RuntimeLimitError:
        return
    raise AssertionError("expected full runtime execution event limit")


def test_full_runtime_entrypoint_allows_execution_without_limit():
    p = _program('let x = now_utc()')
    result = runtime_execute(p, max_events=10)
    assert result[0] is p


def test_full_runtime_entrypoint_restores_context_after_failure():
    p = _program('let x = now_utc()')
    try:
        runtime_execute(p, max_events=0)
    except RuntimeLimitError:
        pass
    result = runtime_execute(p)
    assert result[0] is p
