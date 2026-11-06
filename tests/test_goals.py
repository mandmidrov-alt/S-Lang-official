from slang.core import parse, validate, run
from slang.ast import GoalOp

def test_choose_maximizing_is_semantic_selection():
    src = """data people:
    Alice age 22 score 91
    Bob age 17 score 88
    Carol age 31 score 95
    Dave age 25 score 72

best = choose candidate from people where age >= 18 maximizing score
show best
"""
    p = parse(src); validate(p); run(p)
    assert isinstance(p.ast.goals[0], GoalOp)
    assert p._collections['best']['name'] == 'Carol'

def test_choose_minimizing_can_be_composed_with_property_access():
    src = """data people:
    Alice age 22 score 91
    Bob age 17 score 88
    Carol age 31 score 95
    Dave age 25 score 72

closest = choose candidate from people where age >= 18 and score >= 80 minimizing age
show closest.age
"""
    p = parse(src); validate(p); run(p)
    assert p._collections['closest']['name'] == 'Alice'

def test_choose_rejects_non_boolean_constraint():
    p = parse("""data people:
    Alice age 22 score 91

best = choose candidate from people where age maximizing score
""")
    try:
        validate(p)
    except TypeError as e:
        assert 'choose condition must be Boolean' in str(e)
        return
    assert False

def test_choose_requires_scalar_key():
    p = parse("""data people:
    Alice age 22 score 91

best = choose candidate from people maximizing item
""")
    try:
        validate(p)
    except TypeError as e:
        assert 'choose key must be an orderable scalar value' in str(e)
        return
    assert False


def test_find_path_minimizing_cost_is_semantic_goal():
    src = """graph roads:
    A -> B cost 2
    B -> D cost 2
    A -> C cost 1
    C -> D cost 5

route = find path from A to D in roads minimizing cost
show route
"""
    p = parse(src); validate(p); run(p)
    route = p._collections['route']
    assert route.nodes == ('A', 'B', 'D')
    assert route.cost == 4.0

def test_find_path_supports_undirected_edges():
    src = """graph roads:
    A <-> B cost 3
    B <-> C cost 2

route = find path from C to A in roads minimizing cost
"""
    p = parse(src); validate(p); run(p)
    route = p._collections['route']
    assert route.nodes == ('C', 'B', 'A')
    assert route.cost == 5.0

def test_find_path_reports_no_path():
    p = parse("""graph roads:
    A -> B cost 1

route = find path from A to C in roads minimizing cost
""")
    try:
        validate(p); run(p)
    except TypeError as e:
        assert "found no path" in str(e)
        return
    assert False
