from slang.stdlib.collections import partition_values


def test_partition_preserves_order():
    assert partition_values([1, 2, 3, 4, 5], lambda x: x % 2 == 0) == [[2, 4], [1, 3, 5]]
    assert partition_values([5, 3, 4, 1], lambda x: x > 3) == [[5, 4], [3, 1]]


def test_partition_empty_and_edge_cases():
    assert partition_values([], lambda x: True) == [[], []]
    assert partition_values([1, 2], lambda x: x > 9) == [[], [1, 2]]
    assert partition_values([1, 2], lambda x: True) == [[1, 2], []]


def test_partition_requires_callable_predicate():
    import pytest
    with pytest.raises(TypeError):
        partition_values([1, 2], 2)
