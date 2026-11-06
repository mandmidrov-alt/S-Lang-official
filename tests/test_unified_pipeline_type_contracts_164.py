import pytest

from slang.core import parse, validate


def test_where_generic_result_is_constrained_by_pipeline_contract():
    p = parse("""
function choose<T>(x: T) -> T:
    return x
let values = [1, 2, 3]
result = values |> where choose
""")
    with pytest.raises(TypeError, match="where function result"):
        validate(p)


def test_where_generic_function_can_infer_boolean_result():
    p = parse("""
function positive<T>(x: T) -> Boolean:
    return true
let values = [1, 2, 3]
result = values |> where positive
""")
    validate(p)
    assert str(p._collection_types["result"]) == "List<Number>"


def test_conditional_where_uses_same_function_contract():
    p = parse("""
function positive(x: Number) -> Number:
    return x
let values = [1, 2, 3]
result = values |> if true then where positive else map positive
""")
    with pytest.raises(TypeError, match="where function result"):
        validate(p)


def test_map_nested_function_result_unifies_recursively():
    p = parse("""
function wrap<T>(x: T) -> List<T>:
    return [x]
let values = [1, 2, 3]
result = values |> map wrap
""")
    validate(p)
    assert str(p._collection_types["result"]) == "List<List<Number>>"
