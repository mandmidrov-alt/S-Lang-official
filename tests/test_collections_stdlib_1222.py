import pytest

from slang.stdlib.collections import clip_numbers


def test_clip_numbers():
    assert clip_numbers([-3, 0, 4, 9], 0, 5) == [0, 0, 4, 5]
    assert clip_numbers([], 0, 5) == []
    assert clip_numbers([1, 2, 3], 2, 2) == [2, 2, 2]


def test_clip_numbers_rejects_invalid_contracts():
    with pytest.raises(ValueError):
        clip_numbers([1, 2], 5, 1)
    with pytest.raises(TypeError):
        clip_numbers([1, True], 0, 5)
    with pytest.raises(TypeError):
        clip_numbers([1, 2], False, 5)
    with pytest.raises(TypeError):
        clip_numbers([1, 2], 0, True)
