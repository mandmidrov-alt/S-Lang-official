from slang.core import parse, validate
from slang.goal_ir import lower_goals
from slang.goal_plan import analyze_goals
from slang.semantic_graph import build_semantic_graph


def test_goal_directed_transition_is_normalized_into_goal_ir():
    p = parse("""
module test
let upper = 10
sequence path from 1 for up to 4 steps toward upper choosing:
    value + 1
    value + 3
    value * 2
    satisfy candidate <= upper
""")
    validate(p)
    goals = lower_goals(p.ast)
    assert goals[0].kind == "transition"
    assert goals[0].objective == "distance-to-target"
    assert len(goals[0].candidates) == 3
    assert len(goals[0].transition_constraints) == 1


def test_transition_goal_plan_has_one_deterministic_semantic_strategy():
    p = parse("""
sequence path from 1 for up to 3 steps toward 8 choosing:
    value + 1
    value + 2
    value * 2
""")
    validate(p)
    plan = analyze_goals(p.ast)[0]
    assert plan.goal.kind == "transition"
    assert plan.selected_strategy == "goal-directed-transition"
    assert plan.strategy_candidates == ("goal-directed-transition", "search-based-transition")


def test_transition_appears_once_in_semantic_graph():
    p = parse("""
sequence path from 1 for up to 3 steps toward 8 choosing:
    value + 1
    value + 2
    value * 2
""")
    validate(p)
    graph = build_semantic_graph(p.ast)
    assert [n.kind for n in graph.nodes] == ["goal:transition"]
    assert graph.nodes[0].strategy == "goal-directed-transition"
