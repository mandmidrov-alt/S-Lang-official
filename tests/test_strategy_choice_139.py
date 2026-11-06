from slang.core import parse, validate
from textwrap import dedent
from slang.execution_ir import build_execution_ir
from slang.execution_plan import build_execution_plan
from slang.strategy_selection import build_strategy_choices


def _choices(source):
    p = parse(dedent(source))
    validate(p)
    ir = build_execution_ir(p.ast)
    plan = build_execution_plan(ir)
    return build_strategy_choices(plan, ir)


def test_strategy_choice_preserves_ranked_alternatives():
    choices = _choices('''
        data values:
            a value 1
            b value 2
        result = values |> map value * 2
    ''')
    choice = next(c for c in choices if c.node.startswith("result"))
    assert choice.strategy in choice.alternatives
    assert choice.scores
    assert choice.profile in {"sequential", "parallel", "generic"}


def test_parallel_strategy_is_an_explicit_alternative_when_safe():
    choices = _choices('''
        data values:
            a value 1
            b value 2
        result = values |> map value * 2
    ''')
    choice = next(c for c in choices if c.node.startswith("result"))
    assert "sequential-map" in choice.alternatives
    assert "parallel-map" in choice.alternatives


def test_fused_strategy_is_visible_as_an_alternative():
    choices = _choices('''
        data values:
            a value 1
            b value 2
        result = values |> map value * 2 |> sum
    ''')
    choice = next(c for c in choices if c.node.startswith("result"))
    assert any(x.startswith("fused-") for x in choice.alternatives)
