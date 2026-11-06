from slang.stdlib.collections import contains_any_value


def test_contains_any_value_true_and_false():
    assert contains_any_value([1, 2, 3], [9, 3]) is True
    assert contains_any_value([1, 2, 3], [7, 8]) is False


def test_contains_any_value_empty_candidates():
    assert contains_any_value([1, 2, 3], []) is False


def test_contains_any_value_does_not_mutate_inputs():
    values = [1, 2, 3]
    candidates = [3, 4]
    contains_any_value(values, candidates)
    assert values == [1, 2, 3]
    assert candidates == [3, 4]
