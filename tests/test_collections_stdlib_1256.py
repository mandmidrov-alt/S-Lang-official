from slang.stdlib.collections import none_true


def test_none_true_all_false():
    assert none_true([False, False, False]) is True


def test_none_true_with_true_value():
    assert none_true([False, True, False]) is False


def test_none_true_empty_and_input_unchanged():
    values = [False, False]
    assert none_true([]) is True
    assert none_true(values) is True
    assert values == [False, False]
