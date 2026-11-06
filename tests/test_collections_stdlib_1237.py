from slang.stdlib.collections import sliding_windows

def test_sliding_windows_overlap_and_order():
    assert sliding_windows([1, 2, 3, 4, 5], 3, 1) == [[1, 2, 3], [2, 3, 4], [3, 4, 5]]

def test_sliding_windows_step():
    assert sliding_windows([1, 2, 3, 4, 5], 2, 2) == [[1, 2], [3, 4]]

def test_sliding_windows_empty_and_oversized():
    assert sliding_windows([], 2, 1) == []
    assert sliding_windows([1, 2], 3, 1) == []

def test_sliding_windows_validates_size_and_step():
    import pytest
    with pytest.raises(ValueError): sliding_windows([1, 2], 0, 1)
    with pytest.raises(ValueError): sliding_windows([1, 2], 2, 0)
    with pytest.raises(TypeError): sliding_windows([1, 2], "2", 1)
