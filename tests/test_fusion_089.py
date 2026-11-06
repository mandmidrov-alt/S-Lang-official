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


def test_long_pipeline_gets_partial_fusion_candidate():
    ir, plan = _plan('''
data numbers:
    a value 1
    b value 2
    c value 3
    d value 4
filtered = numbers where value >= 1
mapped1 = filtered map value * 2
mapped2 = mapped1 map value + 1
total = mapped2 reduce 0 with acc + item
''')
    assert len(plan.fusion_groups) == 1
    group = plan.fusion_groups[0]
    assert group.mode == "partial"
    assert group.materializes is True
    assert group.fused_prefix_length == 2
    assert group.strategy == "fused-filter-map-then-reduce"
    assert group.nodes[-1] == group.terminal

    choices = build_strategy_choices(plan, ir)
    terminal = next(c for c in choices if c.node == group.terminal)
    assert terminal.strategy == group.strategy


def test_full_fusion_remains_available_for_short_pipeline():
    _, plan = _plan('''
data numbers:
    a value 1
    b value 2
    c value 3
filtered = numbers where value >= 1
mapped = filtered map value * 2
total = mapped reduce 0 with acc + item
''')
    group = plan.fusion_groups[0]
    assert group.mode == "full"
    assert group.materializes is False
    assert group.strategy == "fused-filter-map-reduce"


def test_fusion_cost_model_prefers_full_over_partial_when_both_are_legal():
    from slang.fusion import FusionGroup
    from slang.cost_model import choose_by_cost
    ir, plan = _plan('''
data numbers:
    a value 1
    b value 2
    c value 3
filtered = numbers where value >= 1
mapped = filtered map value * 2
total = mapped reduce 0 with acc + item
''')
    node = next(n for n in ir.nodes if n.binding == plan.fusion_groups[0].terminal)
    decision = choose_by_cost(node, ("fused-filter-map-reduce", "fused-filter-map-then-reduce", "sequential-reduce"))
    assert decision.selected == "fused-filter-map-reduce"
