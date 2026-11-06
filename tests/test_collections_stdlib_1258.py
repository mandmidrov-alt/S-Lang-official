from slang.stdlib.collections import is_not_empty_values

def test_non_empty_and_empty():
    assert is_not_empty_values([1]) is True
    assert is_not_empty_values([]) is False

def test_nested_collection_counts_as_value():
    assert is_not_empty_values([[]]) is True

def test_input_is_not_modified():
    values = [1, 2]
    assert is_not_empty_values(values) is True
    assert values == [1, 2]
