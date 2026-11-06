from slang.stdlib.collections import reject_values


def test_reject_values_preserves_order():
    values = [1, 2, 3, 4, 5]
    assert reject_values(values, lambda value: value % 2 == 0) == [1, 3, 5]


def test_reject_values_empty_and_all_rejected():
    assert reject_values([], lambda value: True) == []
    assert reject_values([1, 2], lambda value: True) == []


def test_reject_values_does_not_mutate_input():
    values = [1, 2, 3]
    reject_values(values, lambda value: value > 1)
    assert values == [1, 2, 3]
