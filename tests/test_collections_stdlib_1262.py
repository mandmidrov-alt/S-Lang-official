from slang.stdlib import has_at_least_values


def test_has_at_least_values_matches_threshold():
    values = [1, 2, 3]
    assert has_at_least_values(values, 0) is True
    assert has_at_least_values(values, 2) is True
    assert has_at_least_values(values, 3) is True
    assert has_at_least_values(values, 4) is False


def test_has_at_least_values_rejects_invalid_count():
    import pytest

    with pytest.raises(TypeError):
        has_at_least_values([1, 2], True)
    with pytest.raises(TypeError):
        has_at_least_values([1, 2], "2")
    with pytest.raises(ValueError):
        has_at_least_values([1, 2], -1)


def test_has_at_least_values_does_not_mutate():
    values = [1, 2, 3]
    original = list(values)
    assert has_at_least_values(values, 2) is True
    assert values == original


def test_has_at_least_values_rejects_fractional_and_non_finite_counts():
    import math
    import pytest

    for invalid in (1.5, math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError):
            has_at_least_values([1, 2, 3], invalid)


def test_has_at_least_values_accepts_integral_float_and_large_integer():
    assert has_at_least_values([1, 2, 3], 2.0) is True
    assert has_at_least_values([1, 2, 3], 3.0) is True
    assert has_at_least_values([], 10**400) is False
