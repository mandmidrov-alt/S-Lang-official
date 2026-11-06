import math

import pytest

from slang.stdlib.collections import chunk, reverse_range_values, skip, take


def test_take_skip_accept_integer_valued_numbers():
    assert take([1, 2, 3], 2.0) == [1, 2]
    assert skip([1, 2, 3], 1.0) == [2, 3]


def test_take_skip_reject_fractional_counts_instead_of_silently_truncating():
    with pytest.raises(ValueError, match="whole-number"):
        take([1, 2, 3], 1.5)
    with pytest.raises(ValueError, match="whole-number"):
        skip([1, 2, 3], 1.5)


def test_chunk_rejects_non_finite_and_fractional_sizes():
    for value in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="finite"):
            chunk([1, 2], value)
    with pytest.raises(ValueError, match="whole-number"):
        chunk([1, 2], 1.5)


def test_reverse_range_requires_finite_whole_number_bounds():
    for value in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="finite"):
            reverse_range_values([1, 2, 3], value, 2)
    with pytest.raises(ValueError, match="whole-number"):
        reverse_range_values([1, 2, 3], 0, 1.5)


def test_empty_collection_boundaries_are_consistent():
    assert take([], 3) == []
    assert skip([], 3) == []
    assert chunk([], 3) == []
    assert reverse_range_values([], -5, 10) == []


def test_negative_counts_remain_rejected():
    with pytest.raises(ValueError, match="cannot be negative"):
        take([1], -1)
    with pytest.raises(ValueError, match="cannot be negative"):
        skip([1], -1)
