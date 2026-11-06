import pytest

from slang.stdlib.collections import z_scores_numbers


def test_z_scores_numbers():
    result = z_scores_numbers([1, 2, 3])
    assert result[0] == pytest.approx(-1.22474487139)
    assert result[1] == pytest.approx(0.0)
    assert result[2] == pytest.approx(1.22474487139)


def test_z_scores_empty_and_constant():
    assert z_scores_numbers([]) == []
    assert z_scores_numbers([5, 5, 5]) == [0.0, 0.0, 0.0]


def test_z_scores_rejects_bool():
    with pytest.raises(TypeError):
        z_scores_numbers([1, True])
