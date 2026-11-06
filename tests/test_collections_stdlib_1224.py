import pytest

from slang.stdlib.collections import index_of_number, last_index_of_number

def test_numeric_index_lookup():
    assert index_of_number([4, 2, 4, 7, 4], 4) == 0
    assert last_index_of_number([4, 2, 4, 7, 4], 4) == 4
    assert index_of_number([1, 2], 9) == -1
    assert last_index_of_number([], 9) == -1

def test_numeric_index_lookup_contracts():
    with pytest.raises(TypeError):
        index_of_number([1, True], 1)
    with pytest.raises(TypeError):
        last_index_of_number([1, 2], False)
