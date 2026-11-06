from slang.stdlib.collections import find_first, find_last

def test_predicate_search():
    assert find_first([1, 2, 3, 4], lambda x: x > 2) == 2
    assert find_last([1, 2, 3, 4, 3], lambda x: x == 3) == 4
    assert find_first([1, 2], lambda x: x > 9) == -1
    assert find_last([], lambda x: True) == -1

def test_invalid_predicate():
    import pytest
    with pytest.raises(TypeError):
        find_first([1, 2], 2)
