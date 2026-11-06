from slang.stdlib.collections import take_until

def test_take_until_stops_before_first_match():
    assert take_until([1, 2, 3, 4], lambda x: x == 3) == [1, 2]

def test_take_until_first_match_and_no_match():
    assert take_until([3, 4], lambda x: x == 3) == []
    assert take_until([1, 2], lambda x: x > 9) == [1, 2]

def test_take_until_empty():
    assert take_until([], lambda x: True) == []

def test_take_until_requires_callable():
    import pytest
    with pytest.raises(TypeError):
        take_until([1, 2], 2)
