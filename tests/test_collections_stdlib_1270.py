from slang.stdlib import reverse_range_values


def test_reverse_range_values_reverses_half_open_range():
    assert reverse_range_values([1, 2, 3, 4, 5], 1, 4) == [1, 4, 3, 2, 5]


def test_reverse_range_values_clamps_bounds():
    assert reverse_range_values([1, 2, 3], -5, 10) == [3, 2, 1]


def test_reverse_range_values_empty_or_reversed_range_is_unchanged():
    assert reverse_range_values([1, 2, 3], 2, 2) == [1, 2, 3]
    assert reverse_range_values([1, 2, 3], 3, 1) == [1, 2, 3]


def test_reverse_range_values_does_not_mutate_input():
    values = [1, 2, 3, 4]
    result = reverse_range_values(values, 1, 3)
    assert result == [1, 3, 2, 4]
    assert values == [1, 2, 3, 4]
