from slang.stdlib import rotate_values
from slang.stdlib.registry import get, signatures
from slang.stdlib.catalog import entries


def test_rotate_values_left():
    assert rotate_values([1, 2, 3, 4], 1) == [2, 3, 4, 1]


def test_rotate_values_right():
    assert rotate_values([1, 2, 3, 4], -1) == [4, 1, 2, 3]


def test_rotate_values_wraps_and_empty():
    assert rotate_values([1, 2, 3], 4) == [2, 3, 1]
    assert rotate_values([], 4) == []


def test_rotate_values_does_not_mutate():
    values = [1, 2, 3]
    rotate_values(values, 1)
    assert values == [1, 2, 3]


def test_rotate_values_public_api():
    assert get("rotate_values") is not None
    assert "rotate_values" in signatures()
    assert any(entry["name"] == "rotate_values" for entry in entries())
