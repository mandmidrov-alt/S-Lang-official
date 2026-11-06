from slang.stdlib.collections import unzip_values


def test_unzip_values_splits_pairs():
    assert unzip_values([[1, "one"], [2, "two"], [3, "three"]]) == [[1, 2, 3], ["one", "two", "three"]]


def test_unzip_values_empty_input():
    assert unzip_values([]) == [[], []]


def test_unzip_values_rejects_non_pairs():
    try:
        unzip_values([[1, 2, 3]])
    except ValueError as exc:
        assert "exactly two values" in str(exc)
    else:
        raise AssertionError("expected ValueError")
