from slang.core import parse, validate, goal_ir
from slang.goal_ir import lower_goals


def test_all_goal_kinds_lower_to_one_ir():
    p = parse('''
data people:
    Alice age 22 score 91
    Bob age 17 score 88
best = choose candidate from people maximizing score

graph roads:
    A -> B cost 2
    B -> C cost 3
route = find path from A to C in roads minimizing cost

solution = satisfy:
    x in 1..3
    y in 1..3
    x + y == 4
''')
    validate(p)
    goals = lower_goals(p.ast)
    assert [g.kind for g in goals] == ["select", "path", "satisfy"]
    assert goals[0].result == "best"
    assert goals[0].source == "people"
    assert goals[1].start == "A" and goals[1].end == "C"
    assert goals[2].variables == (("x", 1, 3), ("y", 1, 3))


def test_goal_ir_is_stable_and_human_readable():
    p = parse('''
data people:
    Alice age 22 score 91
    Bob age 17 score 88
best = choose candidate from people maximizing score
''')
    validate(p)
    text = goal_ir(p)
    assert 'goal "best" kind=select' in text
    assert 'source = people' in text
    assert 'objective = maximizing' in text
