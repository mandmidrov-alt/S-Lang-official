from slang.stdlib import sort_values


def test_sort_values_orders_numbers_without_mutating_input():
    values = [5, 2, 4, 1, 3]
    assert sort_values(values) == [1, 2, 3, 4, 5]
    assert values == [5, 2, 4, 1, 3]


def test_sort_values_empty_and_singleton():
    assert sort_values([]) == []
    assert sort_values([7]) == [7]


def test_sort_values_is_stable_for_equal_keys():
    values = [(1, "a"), (1, "b"), (0, "c")]
    assert sort_values(values) == [(0, "c"), (1, "a"), (1, "b")]
