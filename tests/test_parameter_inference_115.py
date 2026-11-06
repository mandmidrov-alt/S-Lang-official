import pytest
from slang.core import parse, validate, run


def test_parameter_inference_propagates_through_call_chain():
    p = parse('''function add_one(x: Number) -> Number:
    return x + 1

function middle(x) -> Number:
    return add_one(x)

function outer(x) -> Number:
    return middle(x)

let value = outer(7)
''')
    validate(p)
    run(p)
    assert p._bindings["value"] == 8


def test_generic_call_chain_preserves_inferred_parameter_type():
    p = parse('''function identity(value: T) -> T:
    return value

function middle(value):
    return identity(value)

function outer(value):
    return middle(value)

let value = outer("hello")
''')
    validate(p)
    run(p)
    assert p._bindings["value"] == "hello"


def test_inference_propagates_across_multiple_call_sites():
    p = parse('''function add_one(x: Number) -> Number:
    return x + 1

function middle(x) -> Number:
    return add_one(x)

function outer(x) -> Number:
    return middle(x)

let a = outer(1)
let b = outer(2)
''')
    validate(p)
    run(p)
    assert p._bindings["a"] == 2
    assert p._bindings["b"] == 3


def test_conflicting_types_propagated_through_call_chain_are_rejected():
    p = parse('''function identity(x: T) -> T:
    return x

function middle(x):
    return identity(x)

function outer(x):
    return middle(x)

let a = outer(1)
let b = outer("text")
''')
    with pytest.raises(TypeError, match="conflicting call-site types"):
        validate(p)


def test_unreachable_untyped_parameter_still_requires_annotation():
    p = parse('''function helper(x):
    return x

function main(value: Number) -> Number:
    return value + 1

let result = main(4)
''')
    with pytest.raises(TypeError, match="cannot infer parameter type"):
        validate(p)
