from slang.core import parse
from slang.compiler_pipeline import compile_semantic_pipeline


def test_global_plan_reports_whole_graph_search_metadata():
    p = parse('''
data numbers:
    a value 1
    b value 2
    c value 3
filtered = numbers where value >= 1
mapped = filtered map value * 2
total = mapped reduce 0 with acc + item
''')
    g = compile_semantic_pipeline(p.ast).global_plan_cost
    assert g is not None
    assert g.search_mode == "exhaustive"
    assert g.strategy_combinations_evaluated >= 1
    assert g.strategy_search_space >= g.strategy_combinations_evaluated
    assert g.global_optimality == "exhaustive"


def test_global_plan_whole_graph_search_is_deterministic():
    p = parse('''
data numbers:
    a value 1
    b value 2
    c value 3
filtered = numbers where value >= 1
mapped = filtered map value * 2
total = mapped reduce 0 with acc + item
''')
    a = compile_semantic_pipeline(p.ast).global_plan_cost
    b = compile_semantic_pipeline(p.ast).global_plan_cost
    assert a == b
