from slang.core import parse, run


def test_select_goal_uses_goal_ir_after_collection_dataflow():
    p = parse('''
data people:
    Alice age 22 score 91
    Bob age 17 score 99
    Carol age 31 score 95
adults = people where age >= 18
best = choose candidate from adults maximizing score
show best
''')
    run(p)
    assert p._collections["best"]["name"] == "Carol"



def test_goal_result_can_feed_constraint_solver():
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
    run(p)
    assert p._collections["best"]["name"] == "Carol"
    assert p._collections["solution"] == {"x": 1, "y": 30}
