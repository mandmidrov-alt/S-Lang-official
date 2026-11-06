from slang.core import parse, show_expr_value
from slang.runtime import execute


def test_plan_runtime_executes_function_body_with_if_and_return():
    p = parse('''
function classify(x: Number) -> Number:
    if x > 10:
        return x * 2
    else:
        return x + 1
result = classify(7)
show result
''')
    p, trace = execute(p)
    assert trace.executor == "plan-runtime-segmented"
    assert p._bindings["result"] == 8
    assert show_expr_value(p, p.show_exprs[0]) == "8"


def test_plan_runtime_executes_nested_function_calls():
    p = parse('''
function double(x: Number) -> Number:
    return x * 2
function quad(x: Number) -> Number:
    let y = double(x)
    return double(y)
result = quad(3)
show result
''')
    p, trace = execute(p)
    assert trace.executor == "plan-runtime-segmented"
    assert p._bindings["result"] == 12


def test_plan_runtime_executes_function_inside_collection_pipeline():
    p = parse('''
function double(x: Number) -> Number:
    return x * 2
let values = [1, 2, 3]
result = values |> map double
show result
''')
    p, trace = execute(p)
    assert trace.executor == "plan-runtime-segmented"
    assert p._collections["result"] == [2, 4, 6]


def test_unified_runtime_executes_user_property_body():
    p = parse('''
entity Planet:
    radius: m

property Planet.diameter -> m:
    return self.radius * 2

let earth = Planet(6 m)
show earth.diameter
''')
    p, trace = execute(p)
    assert trace.executor == "plan-runtime-segmented"
    assert show_expr_value(p, p.show_exprs[0]) == "12 m"


def test_unified_runtime_property_can_call_planned_function():
    p = parse('''
entity Planet:
    radius: m

function twice(x: m) -> m:
    return x * 2

property Planet.diameter -> m:
    return twice(self.radius)

let earth = Planet(7 m)
show earth.diameter
''')
    p, trace = execute(p)
    assert trace.executor == "plan-runtime-segmented"
    assert show_expr_value(p, p.show_exprs[0]) == "14 m"


def test_unified_runtime_nested_properties_stay_in_plan_runtime():
    p = parse('''
entity Planet:
    radius: m

property Planet.diameter -> m:
    return self.radius * 2

property Planet.circumference -> m:
    return self.diameter * 3

let earth = Planet(4 m)
show earth.circumference
''')
    p, trace = execute(p)
    assert trace.executor == "plan-runtime-segmented"
    assert show_expr_value(p, p.show_exprs[0]) == "24 m"
