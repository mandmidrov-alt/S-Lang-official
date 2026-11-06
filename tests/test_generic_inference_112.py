from pathlib import Path
from slang.core import parse, validate, run


def test_generic_parameters_can_be_inferred_from_signature():
    src = '''
function identity(value: T) -> T:
    return value

function first_value(values: List<T>) -> T:
    return first(values)

let n = identity(42)
let text = identity("hello")
let first = first_value([10, 20, 30])
'''
    p = parse(src, Path.cwd())
    validate(p)
    run(p)
    assert p._bindings["n"] == 42
    assert p._bindings["text"] == "hello"
    assert p._bindings["first"] == 10


def test_inferred_generic_parameter_is_unified_across_signature():
    src = '''
function append_value(values: List<T>, value: T) -> List<T>:
    return append(values, value)

let numbers = [1, 2]
let bad = append_value(numbers, "x")
'''
    p = parse(src, Path.cwd())
    try:
        validate(p)
    except TypeError as exc:
        assert "argument 2 of 'append_value'" in str(exc)
    else:
        raise AssertionError("expected inferred generic mismatch")


def test_named_type_is_not_mistaken_for_an_implicit_generic():
    src = '''
record T:
    value: Number

function identity(value: T) -> T:
    return value

let item = identity(T(7))
'''
    p = parse(src, Path.cwd())
    validate(p)
    run(p)
    assert p._bindings["item"].type_name == "T"
    assert p._bindings["item"]["value"] == 7


def test_implicit_generic_must_be_inferable_from_arguments():
    src = '''
function impossible() -> T:
    return 1
'''
    p = parse(src, Path.cwd())
    try:
        validate(p)
    except TypeError as exc:
        assert "cannot be inferred from arguments" in str(exc)
    else:
        raise AssertionError("expected uninferable implicit generic rejection")


def test_generic_function_can_infer_return_type_from_body():
    src = '''
function identity(value: T):
    return value

function first_value(values: List<T>):
    return first(values)

let n = identity(42)
let text = identity("hello")
let first = first_value([10, 20, 30])
'''
    p = parse(src, Path.cwd())
    validate(p)
    run(p)
    assert p._bindings["n"] == 42
    assert p._bindings["text"] == "hello"
    assert p._bindings["first"] == 10


def test_non_generic_function_can_infer_return_type_from_body():
    src = '''
function double(x: Number):
    return x + x

let value = double(7)
'''
    p = parse(src, Path.cwd())
    validate(p)
    run(p)
    assert p._bindings["value"] == 14


def test_inference_propagates_through_local_generic_chain():
    src = '''
function identity(value: T):
    return value

function unwrap(values) -> Number:
    let nested = identity(values)
    let inner = first(nested)
    return first(inner)

let value = unwrap([[7, 8]])
'''
    p = parse(src, Path.cwd())
    validate(p)
    run(p)
    assert p._bindings["value"] == 7


def test_inference_propagates_through_local_function_result():
    src = '''
function first_number(values: List<Number>) -> Number:
    return first(values)

function unwrap(values) -> Number:
    let value = first_number(values)
    return value

let result = unwrap([10, 20])
'''
    p = parse(src, Path.cwd())
    validate(p)
    run(p)
    assert p._bindings["result"] == 10


def test_nested_generic_local_conflict_is_rejected():
    src = '''
function first_number(values: List<Number>) -> Number:
    return first(values)

function unwrap(values) -> Number:
    let value = first_number(values)
    return value

let result = unwrap(["x", "y"])
'''
    p = parse(src, Path.cwd())
    try:
        validate(p)
    except TypeError as exc:
        assert "conflicting call-site types" in str(exc)
    else:
        raise AssertionError("expected nested generic conflict")
