import pytest

from slang.stdlib import running_values_right
from slang.stdlib.catalog import entries
from slang.stdlib.registry import get, signatures

def test_running_values_right_uses_last_value_as_seed():
    assert running_values_right([1, 2, 3, 4], lambda total, value: total + value) == [10, 9, 7, 4]

def test_running_values_right_preserves_order_and_input():
    values = [2, 3, 4]
    assert running_values_right(values, lambda total, value: total * value) == [24, 12, 4]
    assert values == [2, 3, 4]

def test_running_values_right_empty_returns_empty():
    assert running_values_right([], lambda total, value: total + value) == []

def test_running_values_right_rejects_non_callable():
    with pytest.raises(TypeError):
        running_values_right([1], 1)

def test_running_values_right_public_api():
    assert get("running_values_right") is not None
    assert "running_values_right" in signatures()
    assert any(entry["name"] == "running_values_right" for entry in entries())
