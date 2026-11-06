from slang.stdlib.collections import enumerate_values


def test_enumerate_values_returns_zero_based_pairs():
    assert enumerate_values(["a", "b", "c"]) == [[0, "a"], [1, "b"], [2, "c"]]


def test_enumerate_values_empty():
    assert enumerate_values([]) == []


def test_enumerate_values_preserves_values():
    values = [10, 20, 10]
    assert enumerate_values(values) == [[0, 10], [1, 20], [2, 10]]
