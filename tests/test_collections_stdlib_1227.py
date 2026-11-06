from slang.stdlib.collections import find_all_indices


def test_find_all_indices_preserves_order():
    assert find_all_indices([1, 2, 3, 4, 5], lambda x: x % 2 == 0) == [1, 3]
    assert find_all_indices([5, 3, 4, 1], lambda x: x > 3) == [0, 2]


def test_find_all_indices_empty_and_no_matches():
    assert find_all_indices([], lambda x: True) == []
    assert find_all_indices([1, 2], lambda x: x > 9) == []


def test_find_all_indices_requires_callable_predicate():
    import pytest
    with pytest.raises(TypeError):
        find_all_indices([1, 2], 2)
