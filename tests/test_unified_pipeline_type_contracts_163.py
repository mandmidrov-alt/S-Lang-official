import pytest

from slang.core import parse, validate


def test_map_first_class_function_uses_unified_parameter_type():
    p = parse("""
function double(x: Number) -> Number:
    return x * 2
let values = [1, 2, 3]
result = values |> map double
""")
    validate(p)
    assert str(p._collection_types["result"]) == "List<Number>"


def test_map_rejects_function_with_incompatible_input_type():
    p = parse("""
function upper(x: Text) -> Text:
    return x
let values = [1, 2, 3]
result = values |> map upper
""")
    with pytest.raises(TypeError, match="map function parameter"):
        validate(p)


def test_where_first_class_function_is_checked_against_item_type():
    p = parse("""
function positive(x: Number) -> Boolean:
    return x > 0
let values = [1, 2, 3]
result = values |> where positive
""")
    validate(p)
    assert str(p._collection_types["result"]) == "List<Number>"


def test_where_rejects_incompatible_function_input():
    p = parse("""
function nonempty(x: Text) -> Boolean:
    return true
let values = [1, 2, 3]
result = values |> where nonempty
""")
    with pytest.raises(TypeError, match="where function parameter"):
        validate(p)


def test_generic_function_value_is_specialized_by_map_item_type():
    p = parse("""
function identity<T>(x: T) -> T:
    return x
let values = [1, 2, 3]
result = values |> map identity
""")
    validate(p)
    assert str(p._collection_types["result"]) == "List<Number>"
