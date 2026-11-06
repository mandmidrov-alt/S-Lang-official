import pytest

from slang.stdlib import running_values
from slang.stdlib.catalog import entries
from slang.stdlib.registry import get, signatures


def test_running_values_uses_first_value_as_seed():
    assert running_values([1, 2, 3, 4], lambda total, value: total + value) == [1, 3, 6, 10]


def test_running_values_preserves_order_and_input():
    values = [2, 3, 4]
    assert running_values(values, lambda total, value: total * value) == [2, 6, 24]
    assert values == [2, 3, 4]


def test_running_values_empty_returns_empty():
    assert running_values([], lambda total, value: total + value) == []


def test_running_values_rejects_non_callable():
    with pytest.raises(TypeError):
        running_values([1], 1)


def test_running_values_public_api():
    assert get("running_values") is not None
    assert "running_values" in signatures()
    assert any(entry["name"] == "running_values" for entry in entries())
