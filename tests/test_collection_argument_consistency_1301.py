import math
import pytest

from slang.stdlib.collections import (
    chunk_exact,
    has_at_most_values,
    has_exactly_values,
    rotate_values,
    sliding_windows,
    split_at_values,
    take_every_from_values,
    take_every_values,
)


@pytest.mark.parametrize("function,args", [
    (take_every_values, ([1, 2, 3], 1.5)),
    (take_every_from_values, ([1, 2, 3], 1.5, 0)),
    (take_every_from_values, ([1, 2, 3], 1, 0.5)),
    (split_at_values, ([1, 2, 3], 1.5)),
    (rotate_values, ([1, 2, 3], 1.5)),
    (chunk_exact, ([1, 2, 3], 1.5)),
    (sliding_windows, ([1, 2, 3], 1.5)),
    (sliding_windows, ([1, 2, 3], 2, 0.5)),
    (has_at_most_values, ([1, 2, 3], 2.5)),
    (has_exactly_values, ([1, 2, 3], 3.5)),
])
def test_collection_integer_arguments_reject_fractional_values(function, args):
    with pytest.raises(ValueError, match="whole-number"):
        function(*args)


@pytest.mark.parametrize("function,args", [
    (take_every_values, ([1, 2], math.inf)),
    (split_at_values, ([1, 2], math.nan)),
    (rotate_values, ([1, 2], -math.inf)),
    (chunk_exact, ([1, 2], math.inf)),
    (sliding_windows, ([1, 2], 1, math.nan)),
    (has_at_most_values, ([1, 2], math.inf)),
])
def test_collection_integer_arguments_reject_non_finite_values(function, args):
    with pytest.raises(ValueError, match="finite"):
        function(*args)


def test_integral_float_arguments_and_empty_collections_remain_supported():
    assert take_every_values([1, 2, 3, 4], 2.0) == [1, 3]
    assert take_every_from_values([1, 2, 3], 2.0, 1.0) == [2]
    assert split_at_values([], 0.0) == [[], []]
    assert rotate_values([], 0.0) == []
    assert chunk_exact([], 2.0) == []
    assert sliding_windows([], 2.0, 1.0) == []
    assert has_at_most_values([], 0.0) is True
    assert has_exactly_values([], 0.0) is True


@pytest.mark.parametrize("function,args", [
    (take_every_values, ([1, 2], True)),
    (split_at_values, ([1, 2], False)),
    (rotate_values, ([1, 2], True)),
    (chunk_exact, ([1, 2], False)),
    (sliding_windows, ([1, 2], True)),
    (has_at_most_values, ([1, 2], False)),
])
def test_collection_integer_arguments_reject_booleans(function, args):
    with pytest.raises(TypeError, match="numeric"):
        function(*args)
