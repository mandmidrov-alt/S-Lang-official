from slang.stdlib.collections import take_while


def test_take_while_returns_longest_prefix():
    assert take_while([2, 4, 6, 7, 8], lambda x: x % 2 == 0) == [2, 4, 6]


def test_take_while_empty_and_full_matches():
    assert take_while([], lambda x: True) == []
    assert take_while([1, 2, 3], lambda x: x > 0) == [1, 2, 3]
    assert take_while([1, 2, 3], lambda x: x < 0) == []


def test_take_while_stops_at_first_failure():
    assert take_while([1, 2, 0, 3], lambda x: x > 0) == [1, 2]


def test_take_while_requires_callable_predicate():
    import pytest
    with pytest.raises(TypeError):
        take_while([1, 2], 2)
