from slang.stdlib.collections import find_all


def test_find_all_preserves_order_and_filters():
    assert find_all([1, 2, 3, 4, 5], lambda x: x % 2 == 0) == [2, 4]
    assert find_all([5, 3, 4, 1], lambda x: x > 3) == [5, 4]


def test_find_all_empty_and_no_matches():
    assert find_all([], lambda x: True) == []
    assert find_all([1, 2], lambda x: x > 9) == []


def test_find_all_requires_callable_predicate():
    import pytest
    with pytest.raises(TypeError):
        find_all([1, 2], 2)
