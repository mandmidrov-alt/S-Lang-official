import pytest
from slang.core import parse, validate, run


def test_infers_parameter_through_nested_generic_call_from_return_type():
    p = parse('''
function first_number(values: List<Number>) -> Number:
    return first(values)

function unwrap(values) -> Number:
    return first_number(values)

let result = unwrap([10, 20, 30])
''')
    validate(p)
    run(p)
    assert p._bindings["result"] == 10


def test_infers_parameter_through_nested_expression():
    p = parse('''
function add_one(x: Number) -> Number:
    return x + 1

function twice(x) -> Number:
    return add_one(add_one(x))

let result = twice(5)
''')
    validate(p)
    run(p)
    assert p._bindings["result"] == 7


def test_infers_parameter_from_explicit_numeric_return_constraint_without_top_level_call():
    p = parse('''
function add_one(x: Number) -> Number:
    return x + 1

function constrained(x) -> Number:
    return add_one(x)

''')
    validate(p)


def test_does_not_guess_parameter_from_boolean_comparison():
    p = parse('''
function check(x) -> Boolean:
    return x > 0

''')
    with pytest.raises(TypeError, match="cannot infer parameter type"):
        validate(p)
