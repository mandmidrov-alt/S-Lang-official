from slang.stdlib import take_every_from_values


def test_take_every_from_values_uses_start_index():
    assert take_every_from_values([10, 20, 30, 40, 50], 2, 1) == [20, 40]


def test_take_every_from_values_handles_bounds():
    assert take_every_from_values([1, 2, 3], 2, 5) == []
    assert take_every_from_values([], 2, 0) == []


def test_take_every_from_values_rejects_invalid_arguments():
    import pytest
    with pytest.raises(ValueError):
        take_every_from_values([1, 2], 0, 0)
    with pytest.raises(ValueError):
        take_every_from_values([1, 2], 1, -1)
