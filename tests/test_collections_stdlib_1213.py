from slang.stdlib.collections import cumulative_average_numbers, percent_change_numbers

def test_cumulative_average_numbers():
    assert cumulative_average_numbers([2, 4, 8]) == [2.0, 3.0, 14 / 3]
    assert cumulative_average_numbers([]) == []

def test_percent_change_numbers():
    assert percent_change_numbers([100, 110, 99]) == [10.0, -10.0]
    assert percent_change_numbers([5]) == []
    assert percent_change_numbers([]) == []

def test_numeric_contracts():
    for fn in (cumulative_average_numbers, percent_change_numbers):
        try:
            fn([1, True])
        except TypeError:
            pass
        else:
            raise AssertionError("expected TypeError")

def test_percent_change_rejects_zero_previous():
    try:
        percent_change_numbers([0, 1])
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError")
