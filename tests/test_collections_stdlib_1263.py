from slang.stdlib import has_at_most_values


def test_has_at_most_values_matches_threshold():
    values = [1, 2, 3]
    assert has_at_most_values(values, 0) is False
    assert has_at_most_values(values, 2) is False
    assert has_at_most_values(values, 3) is True
    assert has_at_most_values(values, 4) is True


def test_has_at_most_values_rejects_invalid_count():
    import pytest

    with pytest.raises(TypeError):
        has_at_most_values([1, 2], True)
    with pytest.raises(TypeError):
        has_at_most_values([1, 2], "2")
    with pytest.raises(ValueError):
        has_at_most_values([1, 2], -1)


def test_has_at_most_values_does_not_mutate():
    values = [1, 2, 3]
    original = list(values)
    assert has_at_most_values(values, 3) is True
    assert values == original
