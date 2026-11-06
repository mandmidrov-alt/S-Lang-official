import pytest

from slang.stdlib.collections import flatten_one


def test_flatten_one_preserves_order():
    assert flatten_one([[1, 2], [3], [4, 5]]) == [1, 2, 3, 4, 5]


def test_flatten_one_empty_groups():
    assert flatten_one([[], [1], [], [2, 3]]) == [1, 2, 3]


def test_flatten_one_requires_nested_lists():
    with pytest.raises(TypeError):
        flatten_one([1, 2])
