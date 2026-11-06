from slang.stdlib.collections import contains_value


def test_contains_value_found_and_missing():
    values = [1, 2, 3]
    assert contains_value(values, 2) is True
    assert contains_value(values, 9) is False


def test_contains_value_empty_collection():
    assert contains_value([], "x") is False


def test_contains_value_does_not_mutate_input():
    values = ["a", "b"]
    assert contains_value(values, "a") is True
    assert values == ["a", "b"]
