from slang.stdlib import is_single_value


def test_is_single_value_for_exactly_one_item():
    assert is_single_value([42]) is True


def test_is_single_value_for_empty_and_multiple_items():
    assert is_single_value([]) is False
    assert is_single_value([1, 2]) is False


def test_is_single_value_does_not_mutate_input():
    values = ["only"]
    assert is_single_value(values) is True
    assert values == ["only"]
