from pathlib import Path
from slang.core import parse_file, validate
from slang.execution_ir import build_execution_ir
from slang.execution_plan import build_execution_plan
from slang.strategy_selection import build_strategy_choices

ROOT = Path(__file__).resolve().parents[1]

def choices(name):
    p = parse_file(ROOT / "examples" / name)
    validate(p)
    ir = build_execution_ir(p.ast)
    plan = build_execution_plan(ir)
    return build_strategy_choices(plan, ir)

def test_strategy_selection_is_deterministic():
    a = choices("goal_ir.sl")
    b = choices("goal_ir.sl")
    assert a == b

def test_goal_strategies_are_selected():
    got = {x.strategy for x in choices("goal_ir.sl")}
    assert "goal-scan-select" in got
    assert "graph-shortest-path" in got
    assert "constraint-propagation" in got

def test_collection_strategies_are_semantic():
    got = {x.strategy for x in choices("data_generic.sl")}
    assert got
    assert all(x.strategy != "generic" for x in choices("data_generic.sl") if x.node.startswith(("filtered", "mapped")))

def test_algorithm_candidates_are_semantically_legal():
    from slang.strategy_selection import algorithm_candidates
    ir = choices("data_generic.sl")
    assert ir
    p = parse_file(ROOT / "examples" / "data_generic.sl")
    validate(p)
    ex = build_execution_ir(p.ast)
    sort = next(x for x in ex.nodes if x.kind == "sort")
    names = {c.strategy for c in algorithm_candidates(sort)}
    assert "stable-sort" in names
    assert "parallel-stable-sort" in names

def test_satisfy_strategy_selection_prefers_constraint_propagation():
    from slang.strategy_selection import build_strategy_choices
    p = parse_file(ROOT / "examples" / "goal_ir.sl")
    validate(p)
    ir = build_execution_ir(p.ast)
    plan = build_execution_plan(ir)
    choice = next(x for x in build_strategy_choices(plan, ir) if x.node.startswith("solution#"))
    assert choice.strategy == "constraint-propagation"
    assert "constraint-enumeration" in choice.alternatives
