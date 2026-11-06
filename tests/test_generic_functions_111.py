import pytest
from pathlib import Path
from slang.core import parse, validate, run


def test_user_generic_functions_infer_and_substitute_results():
    src = '''
function identity<T>(value: T) -> T:
    return value

function first_value<T>(values: List<T>) -> T:
    return first(values)

function append_value<T>(values: List<T>, value: T) -> List<T>:
    return append(values, value)

let numbers = [1, 2, 3]
let texts = ["a", "b"]
let n = identity(42)
let first_number = first_value(numbers)
let more_numbers = append_value(numbers, 4)
let first_text = first_value(texts)
'''
    p = parse(src, Path.cwd())
    validate(p)
    run(p)
    assert p._bindings["n"] == 42
    assert p._bindings["first_number"] == 1
    assert p._bindings["more_numbers"] == [1, 2, 3, 4]
    assert p._bindings["first_text"] == "a"


def test_user_generic_function_rejects_inconsistent_type_arguments():
    src = '''
function append_value<T>(values: List<T>, value: T) -> List<T>:
    return append(values, value)

let numbers = [1, 2, 3]
let bad = append_value(numbers, "x")
'''
    p = parse(src, Path.cwd())
    with pytest.raises(TypeError, match="argument 2 of 'append_value'"):
        validate(p)


def test_generic_function_can_infer_return_type_without_annotation():
    src = '''
function identity<T>(value: T):
    return value

let value = identity(42)
'''
    p = parse(src, Path.cwd())
    validate(p)
    run(p)
    assert p._bindings["value"] == 42
