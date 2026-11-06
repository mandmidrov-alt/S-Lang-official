from slang.stdlib.collections import contains_all_values


def test_contains_all_values_found():
    assert contains_all_values([1, 2, 3, 4], [1, 3]) is True


def test_contains_all_values_missing_and_empty_required():
    assert contains_all_values([1, 2, 3], [1, 9]) is False
    assert contains_all_values([1, 2, 3], []) is True


def test_contains_all_values_does_not_mutate_inputs():
    values = ["a", "b", "c"]
    required = ["c", "a"]
    assert contains_all_values(values, required) is True
    assert values == ["a", "b", "c"]
    assert required == ["c", "a"]
