from slang.stdlib import is_multiple_values


def test_is_multiple_values_for_two_or_more_items():
    assert is_multiple_values([1, 2]) is True
    assert is_multiple_values([1, 2, 3]) is True


def test_is_multiple_values_for_empty_and_single_item():
    assert is_multiple_values([]) is False
    assert is_multiple_values([42]) is False


def test_is_multiple_values_does_not_mutate_input():
    values = ["a", "b"]
    assert is_multiple_values(values) is True
    assert values == ["a", "b"]
