from slang.stdlib.collections import drop_until

def test_drop_until_starts_at_first_match():
    assert drop_until([1, 2, 3, 4], lambda x: x == 3) == [3, 4]

def test_drop_until_first_match_and_no_match():
    assert drop_until([3, 4], lambda x: x == 3) == [3, 4]
    assert drop_until([1, 2], lambda x: x > 9) == []

def test_drop_until_empty():
    assert drop_until([], lambda x: True) == []

def test_drop_until_requires_callable():
    import pytest
    with pytest.raises(TypeError):
        drop_until([1, 2], 2)

def test_drop_until_preserves_suffix_order():
    assert drop_until([5, 1, 4, 2, 3], lambda x: x % 2 == 0) == [4, 2, 3]

def test_drop_until_does_not_mutate_input():
    values = [1, 2, 3]
    result = drop_until(values, lambda x: x == 2)
    assert values == [1, 2, 3]
    assert result == [2, 3]
