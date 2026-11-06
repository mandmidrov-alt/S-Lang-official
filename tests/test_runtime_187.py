from slang.core import parse, runtime_execute, show_expr_value


def test_pure_binding_with_show_uses_plan_runtime():
    p = parse("""
let x = 2 + 3
show x
""")
    p, trace = runtime_execute(p)
    assert trace.executor == "plan-runtime"
    assert show_expr_value(p, p.show_exprs[0]) == "5"


def test_collection_with_show_uses_plan_runtime():
    p = parse("""
data numbers:
    a value 1
    b value 2
    c value 3
selected = numbers where value >= 2
show selected
""")
    p, trace = runtime_execute(p)
    assert trace.executor == "plan-runtime-specialized"
    assert show_expr_value(p, p.show_exprs[0]) == "[b(value=2), c(value=3)]"


def test_stateful_program_with_show_uses_state_plan_runtime():
    p = parse("""
state total = 1
set total = total + 4
show total
""")
    p, trace = runtime_execute(p)
    assert trace.executor == "plan-runtime-stateful"
    assert show_expr_value(p, p.show_exprs[0]) == "5"


def test_goal_program_with_show_uses_goal_plan_runtime():
    p = parse("""
data people:
    Ada age 30
    Bob age 20
best = choose people from people minimizing age
show best
""")
    p, trace = runtime_execute(p)
    assert trace.executor == "plan-runtime-goals"
    assert show_expr_value(p, p.show_exprs[0]) == "{'name': 'Bob', 'age': 20}"
