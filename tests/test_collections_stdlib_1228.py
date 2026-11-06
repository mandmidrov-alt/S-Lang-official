from slang.stdlib.collections import count_if


def test_count_if_counts_matching_values():
    assert count_if([1, 2, 3, 4, 5], lambda x: x % 2 == 0) == 2
    assert count_if([5, 3, 4, 1], lambda x: x > 3) == 2


def test_count_if_empty_and_no_matches():
    assert count_if([], lambda x: True) == 0
    assert count_if([1, 2], lambda x: x > 9) == 0


def test_count_if_requires_callable_predicate():
    import pytest
    with pytest.raises(TypeError):
        count_if([1, 2], 2)
