from slang.stdlib.collections import is_empty_values

def test_empty_and_nonempty():
    assert is_empty_values([]) is True
    assert is_empty_values([1]) is False

def test_does_not_mutate():
    values = [1, 2]
    assert is_empty_values(values) is False
    assert values == [1, 2]

def test_nested_values_are_supported():
    assert is_empty_values([[]]) is False
