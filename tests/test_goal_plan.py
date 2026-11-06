from slang.core import parse, validate
from slang.goal_plan import analyze_goals, format_goal_plan


def test_goal_dependencies_and_candidates():
    p = parse('''
data people:
    Alice age 22 score 91
    Bob age 17 score 88
best = choose candidate from people where age >= 18 maximizing score
closest = choose candidate from people where age >= 18 minimizing age
''')
    validate(p)
    plans = analyze_goals(p.ast)
    assert plans[0].dependencies == ()
    assert plans[0].external_sources == ("people",)
    assert plans[0].independent is True
    assert "scan" in plans[0].strategy_candidates
    assert plans[1].dependencies == ()


def test_satisfy_plan_candidates():
    p = parse('''
solution = satisfy:
    x in 1..3
    y in 1..3
    x + y == 4
''')
    validate(p)
    plans = analyze_goals(p.ast)
    assert plans[0].strategy_candidates == ("constraint-propagation", "enumeration")


def test_plan_is_explicitly_not_a_strategy_selection():
    p = parse('''
graph roads:
    A -> B cost 2
    B -> C cost 3
route = find path from A to C in roads minimizing cost
''')
    validate(p)
    text = format_goal_plan(analyze_goals(p.ast))
    assert 'strategy_selected = dijkstra' in text
    assert 'strategy.dijkstra = applicable' in text
    assert 'strategy.constraint-propagation' not in text
    assert 'dijkstra' in text
