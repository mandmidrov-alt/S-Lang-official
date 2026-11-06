from slang.stdlib.collections import filter_values


def test_filter_values_preserves_order():
    values = [5, 2, 4, 1, 6]
    assert filter_values(values, lambda value: value % 2 == 0) == [2, 4, 6]


def test_filter_values_empty_and_all_rejected():
    assert filter_values([], lambda value: True) == []
    assert filter_values([1, 2], lambda value: False) == []


def test_filter_values_does_not_mutate_input():
    values = [1, 2, 3]
    filter_values(values, lambda value: value > 1)
    assert values == [1, 2, 3]
