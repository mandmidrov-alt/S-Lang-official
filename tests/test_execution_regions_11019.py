from slang.core import parse
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.selected_execution_plan import format_selected_execution_plan


def test_selected_plan_contains_concrete_execution_regions():
    p = parse('''
data numbers:
    a value 1
    b value 2
filtered = numbers where value >= 1
mapped = filtered map value * 2
''')
    result = compile_semantic_pipeline(p.ast)
    regions = result.selected_execution_plan.execution_regions
    assert regions
    assert all(r.mode in {"streaming", "materialized", "parallel"} for r in regions)
    assert tuple(n for r in regions for n in r.nodes) == tuple(s.node for s in result.selected_execution_plan.steps)


def test_selected_plan_execution_regions_are_deterministic_and_visible():
    p = parse('''
data numbers:
    a value 1
    b value 2
mapped = numbers map value * 2
''')
    a = compile_semantic_pipeline(p.ast).selected_execution_plan
    b = compile_semantic_pipeline(p.ast).selected_execution_plan
    assert a.execution_regions == b.execution_regions
    text = format_selected_execution_plan(a)
    assert "execution_regions =" in text
    assert "execution_region 0:" in text
    assert "mode=" in text
