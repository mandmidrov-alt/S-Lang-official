from slang.stdlib.collections import (
    cumulative_min_numbers, cumulative_max_numbers, differences_numbers,
)

def test_cumulative_min_numbers():
    assert cumulative_min_numbers([4, 2, 3, 1]) == [4, 2, 2, 1]
    assert cumulative_min_numbers([]) == []

def test_cumulative_max_numbers():
    assert cumulative_max_numbers([1, 3, 2, 5]) == [1, 3, 3, 5]
    assert cumulative_max_numbers([]) == []

def test_differences_numbers():
    assert differences_numbers([10, 13, 9, 9]) == [3, -4, 0]
    assert differences_numbers([5]) == []
    assert differences_numbers([]) == []

def test_numeric_contracts():
    for fn in (cumulative_min_numbers, cumulative_max_numbers, differences_numbers):
        try:
            fn([1, True])
        except TypeError:
            pass
        else:
            raise AssertionError("expected TypeError")
