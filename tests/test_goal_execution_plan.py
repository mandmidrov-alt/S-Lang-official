from slang.core import parse, run
from slang.goal_plan import build_execution_plan


def test_execution_plan_selects_proven_reference_strategies():
    p = parse('''
data people:
    Alice age 22 score 91
best = choose candidate from people where age >= 18 maximizing score
''')
    plan = build_execution_plan(p.ast)
    assert plan.goals[0].selected_strategy == "scan"
    assert plan.goals[0].strategies[0].applicable is True
    assert plan.goals[0].strategies[1].applicable is False


def test_execution_plan_selects_path_strategy():
    p = parse('''
graph roads:
    A -> B cost 2
    B -> C cost 3
route = find path from A to C in roads minimizing cost
''')
    plan = build_execution_plan(p.ast)
    assert plan.goals[0].selected_strategy == "dijkstra"


def test_execution_plan_selects_finite_satisfy_strategy():
    p = parse('''
solution = satisfy:
    x in 1..3
    y in 1..3
    x + y == 4
''')
    plan = build_execution_plan(p.ast)
    assert plan.goals[0].selected_strategy == "constraint-propagation"


def test_goal_chain_is_represented_in_execution_plan():
    p = parse('''
data people:
    Alice age 22 score 91
    Bob age 17 score 99
best = choose candidate from people where age >= 18 maximizing score
second = choose candidate from best minimizing age
''')
    plan = build_execution_plan(p.ast)
    assert plan.goals[1].dependencies == ("best",)
    run(p)
    assert p._collections["second"]["name"] == "Alice"
