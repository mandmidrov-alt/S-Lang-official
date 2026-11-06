from slang.stdlib import is_unique_values


def test_is_unique_values_for_unique_collection():
    assert is_unique_values([1, 2, 3]) is True


def test_is_unique_values_detects_duplicates():
    assert is_unique_values([1, 2, 1]) is False
    assert is_unique_values(["a", "a"]) is False


def test_is_unique_values_handles_empty_and_unhashable_values():
    assert is_unique_values([]) is True
    assert is_unique_values([[1], [2]]) is True
    assert is_unique_values([[1], [1]]) is False
