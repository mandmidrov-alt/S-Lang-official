from slang.stdlib.collections import drop_while


def test_drop_while_removes_matching_prefix():
    assert drop_while([1, 2, 3, 4], lambda x: x < 3) == [3, 4]


def test_drop_while_all_match_and_none_match():
    assert drop_while([1, 2], lambda x: x < 9) == []
    assert drop_while([1, 2], lambda x: x < 0) == [1, 2]


def test_drop_while_empty():
    assert drop_while([], lambda x: True) == []


def test_drop_while_preserves_suffix_order():
    assert drop_while([1, 1, 4, 2, 3], lambda x: x == 1) == [4, 2, 3]


def test_drop_while_requires_callable_predicate():
    import pytest
    with pytest.raises(TypeError):
        drop_while([1, 2], 2)
