from slang.core import parse
from slang.compiler_pipeline import compile_semantic_pipeline


def test_global_plan_cost_is_exposed_and_deterministic():
    p = parse('''
data numbers:
    a value 1
    b value 2
    c value 3
filtered = numbers where value >= 1
mapped = filtered map value * 2
total = mapped reduce 0 with acc + item
''')
    a = compile_semantic_pipeline(p.ast)
    b = compile_semantic_pipeline(p.ast)
    assert a.global_plan_cost == b.global_plan_cost
    assert a.global_plan_cost is not None
    assert a.global_plan_cost.total_cost >= a.global_plan_cost.local_cost


def test_global_plan_counts_fused_internal_edges():
    p = parse('''
data numbers:
    a value 1
    b value 2
    c value 3
filtered = numbers where value >= 1
mapped = filtered map value * 2
total = mapped reduce 0 with acc + item
''')
    pipeline = compile_semantic_pipeline(p.ast)
    assert pipeline.global_plan_cost is not None
    assert pipeline.global_plan_cost.fused_internal_edges >= 1


def test_global_plan_accounts_for_goal_chain_transition():
    p = parse('''
data people:
    Alice age 22 score 91
    Bob age 17 score 99
    Carol age 31 score 95
best = choose candidate from people where age >= 18 maximizing score
solution = satisfy:
    x in 1..100
    y in 1..100
    x + y == best.age
    x < y
''')
    pipeline = compile_semantic_pipeline(p.ast)
    assert pipeline.global_plan_cost is not None
    assert pipeline.global_plan_cost.chain_cost > 0
    assert pipeline.global_plan_cost.strategy_transitions == 1


def test_global_plan_chain_cost_is_reproducible_for_mixed_goal_pipeline():
    p = parse('''
data people:
    Alice age 22 score 91
    Bob age 17 score 99
    Carol age 31 score 95
best = choose candidate from people where age >= 18 maximizing score
solution = satisfy:
    x in 1..100
    y in 1..100
    x + y == best.age
    x < y
''')
    a = compile_semantic_pipeline(p.ast)
    b = compile_semantic_pipeline(p.ast)
    assert a.global_plan_cost.chain_cost == b.global_plan_cost.chain_cost
    assert a.global_plan_cost.strategy_transitions == b.global_plan_cost.strategy_transitions


def test_global_plan_reports_cardinality_weighted_cost_and_peak():
    p = parse('''
data numbers:
    a value 1
    b value 2
    c value 3
filtered = numbers where value >= 1
mapped = filtered map value * 2
total = mapped reduce 0 with acc + item
''')
    pipeline = compile_semantic_pipeline(p.ast)
    g = pipeline.global_plan_cost
    assert g is not None
    assert g.cardinality_weighted_cost >= 0
    assert g.estimated_peak_cardinality == 3


def test_global_plan_cardinality_weighting_is_deterministic():
    p = parse('''
data numbers:
    a value 1
    b value 2
    c value 3
    d value 4
filtered = numbers where value >= 1
mapped = filtered map value * 2
total = mapped reduce 0 with acc + item
''')
    a = compile_semantic_pipeline(p.ast).global_plan_cost
    b = compile_semantic_pipeline(p.ast).global_plan_cost
    assert a is not None and b is not None
    assert a.cardinality_weighted_cost == b.cardinality_weighted_cost
    assert a.estimated_peak_cardinality == b.estimated_peak_cardinality


def test_global_plan_reports_selectivity_estimates():
    p = parse("""
data numbers:
    a value 1
    b value 2
    c value 3
    d value 4
filtered = numbers where value >= 2
mapped = filtered map value * 2
total = mapped reduce 0 with acc + item
""")
    g = compile_semantic_pipeline(p.ast).global_plan_cost
    assert g is not None
    estimates = dict(g.estimated_selectivities)
    assert 0.66 <= estimates["filtered#1"] <= 0.67
    assert estimates["mapped#1"] == 1.0
    assert g.selectivity_weighted_cost >= 0


def test_filter_selectivity_is_recorded_as_reducing():
    p = parse("""
data numbers:
    a value 1
    b value 2
    c value 3
    d value 4
filtered = numbers where value >= 2
mapped = filtered map value * 2
""")
    pipeline = compile_semantic_pipeline(p.ast)
    nodes = {n.binding: n for n in pipeline.optimized_ir.nodes}
    assert nodes["filtered#1"].kind == "filter"
    assert pipeline.global_plan_cost is not None
    assert dict(pipeline.global_plan_cost.estimated_selectivities )["filtered#1"] < 1.0


def test_filter_selectivity_is_inferred_from_numeric_range():
    p = parse('''
 data numbers:
    a value 0
    b value 25
    c value 50
    d value 75
    e value 100
filtered = numbers where value >= 50
''')
    g = compile_semantic_pipeline(p.ast).global_plan_cost
    assert g is not None
    estimates = dict(g.estimated_selectivities)
    assert 0.49 <= estimates["filtered#1"] <= 0.51


def test_filter_selectivity_can_be_zero_or_one_from_range():
    p = parse('''
 data numbers:
    a value 0
    b value 10
    c value 20
filtered = numbers where value > 100
''')
    g = compile_semantic_pipeline(p.ast).global_plan_cost
    assert g is not None
    assert dict(g.estimated_selectivities)["filtered#1"] == 0.0


def test_choose_selectivity_is_inferred_from_source_range():
    p = parse('''
data people:
    a age 10 score 50
    b age 20 score 70
    c age 30 score 90
    d age 40 score 95
best = choose candidate from people where age >= 30 maximizing score
''')
    g = compile_semantic_pipeline(p.ast).global_plan_cost
    assert g is not None
    estimates = dict(g.estimated_selectivities)
    assert 0.32 <= estimates["best#1"] <= 0.34


def test_satisfy_search_selectivity_uses_constraint_propagation():
    p = parse('''
solution = satisfy:
    x in 1..100
    y in 1..100
    x + y == 150
    x < y
''')
    pipeline = compile_semantic_pipeline(p.ast)
    g = pipeline.global_plan_cost
    assert g is not None
    estimates = dict(g.estimated_selectivities)
    assert estimates["solution#1"] < 1.0
    assert estimates["solution#1"] > 0.0
    nodes = {n.binding: n for n in pipeline.optimized_ir.nodes}
    assert any(h.startswith("satisfy-search-selectivity=") for h in nodes["solution#1"].optimization_hints)


def test_satisfy_search_selectivity_can_be_zero_for_inconsistent_bounds():
    p = parse('''
solution = satisfy:
    x in 1..10
    y in 1..10
    x + y == 100
''')
    pipeline = compile_semantic_pipeline(p.ast)
    g = pipeline.global_plan_cost
    assert g is not None
    assert dict(g.estimated_selectivities)["solution#1"] == 0.0


def test_global_plan_path_uses_declared_graph_size():
    p = parse('''
graph roads:
    A -> B cost 1
    B -> C cost 2
    A -> C cost 5
route = find path from A to C in roads minimizing cost
''')
    pipeline = compile_semantic_pipeline(p.ast)
    node = next(n for n in pipeline.optimized_ir.nodes if n.kind == "goal:path")
    assert "path-graph-nodes=3" in node.optimization_hints
    assert "path-graph-edges=3" in node.optimization_hints
    assert any(h.startswith("path-graph-density=") for h in node.optimization_hints)
    assert pipeline.global_plan_cost is not None
    assert pipeline.global_plan_cost.estimated_selectivities


def test_global_plan_path_metadata_is_deterministic():
    p = parse('''
graph roads:
    A -> B cost 1
    B -> C cost 2
    C -> D cost 3
    A -> D cost 10
route = find path from A to D in roads minimizing cost
''')
    a = compile_semantic_pipeline(p.ast)
    b = compile_semantic_pipeline(p.ast)
    na = next(n for n in a.optimized_ir.nodes if n.kind == "goal:path")
    nb = next(n for n in b.optimized_ir.nodes if n.kind == "goal:path")
    assert na.optimization_hints == nb.optimization_hints
    assert a.global_plan_cost == b.global_plan_cost
