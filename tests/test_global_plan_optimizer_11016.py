from slang.core import parse
from slang.compiler_pipeline import compile_semantic_pipeline


def test_global_plan_accounts_for_strategy_profile_handoffs():
    p = parse("""
data numbers:
    a value 1
    b value 2
    c value 3
filtered = numbers where value >= 1
mapped = filtered map value * 2
""")
    pipeline = compile_semantic_pipeline(p.ast)
    g = pipeline.global_plan_cost
    assert g is not None
    assert g.strategy_combinations_evaluated >= 1
    assert g.strategy_search_space >= 1


def test_strategy_profile_handoff_is_deterministic():
    from slang.global_plan_optimizer import _transition_cost
    sequential_to_parallel = _transition_cost("sequential-map", "parallel-map", "map", "map")
    parallel_to_sequential = _transition_cost("parallel-map", "sequential-map", "map", "map")
    same = _transition_cost("sequential-map", "sequential-map", "map", "map")
    assert same == 0.0
    assert sequential_to_parallel > 0.15
    assert parallel_to_sequential > 0.15
    assert sequential_to_parallel != parallel_to_sequential

def test_global_search_remains_deterministic_with_profile_costs():
    p = parse("""
data numbers:
    a value 1
    b value 2
    c value 3
filtered = numbers where value >= 1
mapped = filtered map value * 2
total = mapped reduce 0 with acc + item
""")
    a = compile_semantic_pipeline(p.ast)
    b = compile_semantic_pipeline(p.ast)
    assert a.global_plan_cost == b.global_plan_cost
    assert a.strategies == b.strategies
