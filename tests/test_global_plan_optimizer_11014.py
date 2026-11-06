from slang.core import parse
from slang.compiler_pipeline import compile_semantic_pipeline

def test_global_plan_exposes_downstream_pressure():
    p = parse("""
graph roads:
    A <-> B cost 1
    B <-> C cost 2
    C <-> D cost 3
route = find path from A to D in roads minimizing cost
show route
""")
    g = compile_semantic_pipeline(p.ast).global_plan_cost
    assert g is not None
    assert dict(g.downstream_pressure)["route#1"] >= 0
    assert g.strategy_context_cost >= 0

def test_global_plan_context_is_deterministic():
    p = parse("""
graph roads:
    A <-> B cost 1
    B <-> C cost 2
    C <-> D cost 3
route = find path from A to D in roads minimizing cost
show route
""")
    a = compile_semantic_pipeline(p.ast).global_plan_cost
    b = compile_semantic_pipeline(p.ast).global_plan_cost
    assert a == b
