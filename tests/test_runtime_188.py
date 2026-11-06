from slang.core import parse, show_expr_value
from slang.runtime import execute


def test_unified_runtime_mixes_state_and_collection_pipeline():
    p = parse('''
state threshold = 2
set threshold = threshold + 1
data numbers:
    a value 1
    b value 3
    c value 5
selected = numbers where value >= 3
show selected
''')
    p, trace = execute(p)
    assert trace.executor == "plan-runtime-segmented"
    assert p._states["threshold"] == 3
    assert show_expr_value(p, p.show_exprs[0]) == "[b(value=3), c(value=5)]"


def test_unified_runtime_mixes_collection_and_goal():
    p = parse('''
data people:
    Ada age 30
    Bob age 20
    Cara age 25
young = people where age < 30
best = choose young from young minimizing age
show best
''')
    p, trace = execute(p)
    assert trace.executor == "plan-runtime-segmented"
    assert show_expr_value(p, p.show_exprs[0]) == "{'name': 'Bob', 'age': 20}"
