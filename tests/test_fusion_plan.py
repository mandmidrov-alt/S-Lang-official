from slang.core import parse
from slang.execution_ir import build_execution_ir
from slang.execution_plan import build_execution_plan
from slang.dependency_graph import build_dependency_graph
from slang.dependency_analysis import analyze_dependency_graph
from slang.strategy_selection import build_strategy_choices


def _plan(source):
    ir = build_execution_ir(parse(source).ast)
    graph = build_dependency_graph(ir)
    analysis = analyze_dependency_graph(ir, graph)
    return ir, build_execution_plan(ir, analysis, graph)


def test_fusion_is_planned_for_filter_map_reduce():
    ir, plan = _plan('''
data numbers:\n    a value 1\n    b value 2\n    c value 3\n    d value 4\nfiltered = numbers where value >= 2\nscaled = filtered map value * 2\ntotal = scaled reduce 0 with acc + item\n''')
    assert len(plan.fusion_groups) == 1
    group = plan.fusion_groups[0]
    assert group.strategy == "fused-filter-map-reduce"
    assert group.terminal.startswith("total#")
    choices = build_strategy_choices(plan, ir)
    terminal = next(c for c in choices if c.node == group.terminal)
    assert terminal.strategy == group.strategy


def test_fusion_requires_single_consumer():
    ir, plan = _plan('''
data numbers:\n    a value 1\n    b value 2\nfiltered = numbers where value >= 2\nscaled = filtered map value * 2\ntotal = scaled reduce 0 with acc + item\nshow filtered\n''')
    assert len(plan.fusion_groups) == 1
    assert plan.fusion_groups[0].strategy == "fused-map-reduce"


def test_fusion_is_deterministic():
    source = '''
data numbers:\n    a value 1\n    b value 2\nfiltered = numbers where value >= 2\nscaled = filtered map value * 2\ntotal = scaled reduce 0 with acc + item\n'''
    a = _plan(source)[1]
    b = _plan(source)[1]
    assert a == b
