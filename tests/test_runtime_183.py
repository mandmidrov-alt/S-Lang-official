from slang.core import parse, validate
from slang.runtime import execute


def test_runtime_executes_goal_select_from_plan():
    p = parse('''
data people:
    alice age 30
    bob age 20
    cara age 40
choice = choose people from people minimizing age
''')
    validate(p)
    module, trace = execute(p)
    assert trace.executor == "plan-runtime-goals"
    assert any(step.strategy == "goal-scan-select" for step in trace.steps)
    assert module._collections["choice"]["name"] == "bob"


def test_runtime_executes_shortest_path_from_plan():
    p = parse('''
graph roads:
    A -> B cost 1
    B -> C cost 2
    A -> C cost 10
path = find path from A to C in roads minimizing cost
''')
    validate(p)
    module, trace = execute(p)
    assert trace.executor == "plan-runtime-goals"
    assert any(step.strategy == "graph-shortest-path" for step in trace.steps)
    assert module._collections["path"].nodes == ("A", "B", "C")
    assert module._collections["path"].cost == 3.0


def test_runtime_executes_constraint_enumeration_from_plan():
    p = parse('''
solution = satisfy:
    x in 1..5
    y in 1..5
    x + y == 6
''')
    validate(p)
    module, trace = execute(p)
    assert trace.executor == "plan-runtime-goals"
    assert any(step.strategy == "constraint-propagation" for step in trace.steps)
    assert module._collections["solution"] == {"x": 1, "y": 5}


def test_runtime_executes_state_transition_from_plan():
    p = parse('''
sequence values from 1 for 5 steps using value + 1
''')
    validate(p)
    module, trace = execute(p)
    assert trace.executor == "plan-runtime-goals"
    assert any(step.strategy == "state-transition" for step in trace.steps)
    assert module._collections["values"] == [1, 2, 3, 4, 5]


def test_runtime_selects_exact_bidirectional_dijkstra_for_eligible_graph():
    p = parse('''
graph roads:
    A <-> B cost 1
    B <-> C cost 2
    A <-> C cost 10
path = find path from A to C in roads minimizing cost
''')
    validate(p)
    module, trace = execute(p)
    assert any(step.strategy == "bidirectional-dijkstra" for step in trace.steps)
    assert module._collections["path"].nodes == ("A", "B", "C")
    assert module._collections["path"].cost == 3.0
