from slang.stdlib.collections import chunk_exact

def test_chunk_exact_drops_partial_tail():
    assert chunk_exact([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4]]

def test_chunk_exact_full_and_empty():
    assert chunk_exact([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]
    assert chunk_exact([], 2) == []

def test_chunk_exact_validates_size():
    import pytest
    with pytest.raises(ValueError): chunk_exact([1, 2], 0)
    with pytest.raises(TypeError): chunk_exact([1, 2], "2")
    with pytest.raises(ValueError): chunk_exact([1, 2], -1)
