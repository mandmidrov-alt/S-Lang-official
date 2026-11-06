from slang.stdlib.collections import map_values

def test_map_values_preserves_order_and_maps():
    assert map_values([1, 2, 3], lambda x: x * 10) == [10, 20, 30]

def test_map_values_supports_type_transformation():
    assert map_values([1, 2, 3], lambda x: f"n={x}") == ["n=1", "n=2", "n=3"]

def test_map_values_empty():
    assert map_values([], lambda x: x) == []

def test_map_values_requires_callable_mapper():
    import pytest
    with pytest.raises(TypeError):
        map_values([1, 2], 2)
