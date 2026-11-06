from slang.stdlib.collections import map_with_index


def test_map_with_index_preserves_order_and_exposes_zero_based_index():
    assert map_with_index([10, 20, 30], lambda value, index: value + index) == [10, 21, 32]


def test_map_with_index_supports_type_transformation():
    assert map_with_index(["a", "b"], lambda value, index: f"{index}:{value}") == ["0:a", "1:b"]


def test_map_with_index_empty():
    assert map_with_index([], lambda value, index: index) == []


def test_map_with_index_requires_callable_mapper():
    import pytest
    with pytest.raises(TypeError):
        map_with_index([1, 2], 2)
