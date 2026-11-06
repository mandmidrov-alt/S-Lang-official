from slang.stdlib.collections import partition_indices


def test_partition_indices_preserves_order():
    assert partition_indices([10, 3, 8, 1, 6], lambda x: x >= 6) == [[0, 2, 4], [1, 3]]


def test_partition_indices_empty_and_edge_cases():
    assert partition_indices([], lambda x: True) == [[], []]
    assert partition_indices([1, 2], lambda x: x > 9) == [[], [0, 1]]
    assert partition_indices([1, 2], lambda x: True) == [[0, 1], []]


def test_partition_indices_requires_callable_predicate():
    import pytest
    with pytest.raises(TypeError):
        partition_indices([1, 2], 2)
