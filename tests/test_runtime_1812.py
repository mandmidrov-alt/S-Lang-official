import slang.core as core
from slang.core import parse
from slang.runtime import execute


def _block_must_not_run(*args, **kwargs):
    raise AssertionError("unified plan runtime reached core._eval_block")


def test_unified_runtime_does_not_reach_reference_block_for_function(monkeypatch):
    monkeypatch.setattr(core, "_eval_block", _block_must_not_run)
    p = parse('''
function classify(x: Number) -> Number:
    if x > 10:
        return x * 2
    else:
        return x + 1
result = classify(7)
show result
''')
    p, trace = execute(p)
    assert trace.executor == "plan-runtime-segmented"
    assert p._bindings["result"] == 8


def test_unified_runtime_does_not_reach_reference_block_for_property(monkeypatch):
    monkeypatch.setattr(core, "_eval_block", _block_must_not_run)
    p = parse('''
entity Planet:
    radius: m

function twice(x: m) -> m:
    return x * 2

property Planet.diameter -> m:
    let d = twice(self.radius)
    return d

let earth = Planet(7 m)
show earth.diameter
''')
    p, trace = execute(p)
    assert trace.executor == "plan-runtime-segmented"
    assert p._bindings["earth"].fields["radius"].value == 7


def test_unified_runtime_does_not_reach_reference_block_for_nested_function_calls(monkeypatch):
    monkeypatch.setattr(core, "_eval_block", _block_must_not_run)
    p = parse('''
function double(x: Number) -> Number:
    return x * 2
function quad(x: Number) -> Number:
    let y = double(x)
    return double(y)
result = quad(3)
''')
    p, trace = execute(p)
    assert trace.executor == "plan-runtime-segmented"
    assert p._bindings["result"] == 12


def test_supported_stateful_runtime_does_not_reach_reference_block(monkeypatch):
    calls = {"count": 0}
    original = core._eval_block

    def counted(*args, **kwargs):
        calls["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(core, "_eval_block", counted)
    p = parse('''
state x = 1
set x = x + 1
show x
''')
    p, trace = execute(p)
    assert trace.executor.startswith("plan-runtime-")
    assert calls["count"] == 0


def _expr_must_not_run(*args, **kwargs):
    raise AssertionError("unified plan runtime reached core._eval_expr")


def test_unified_runtime_does_not_reach_reference_expression_evaluator(monkeypatch):
    monkeypatch.setattr(core, "_eval_expr", _expr_must_not_run)
    p = parse('''
function double(x: Number) -> Number:
    return x * 2
let values = [1, 2, 3]
result = values |> map double |> sum
show result
''')
    p, trace = execute(p)
    assert trace.executor == "plan-runtime-segmented"
    assert p._collections["result"] == 12

