import pytest

from slang.stdlib import scan_values_right
from slang.stdlib.catalog import entries
from slang.stdlib.registry import get, signatures


def test_scan_values_right_returns_results_in_original_order():
    assert scan_values_right([1, 2, 3, 4], 0, lambda total, value: total + value) == [10, 9, 7, 4]


def test_scan_values_right_uses_initial_as_right_seed():
    values = [2, 3]
    assert scan_values_right(values, 10, lambda total, value: total + value) == [15, 13]
    assert values == [2, 3]


def test_scan_values_right_empty_returns_empty():
    assert scan_values_right([], 42, lambda total, value: total + value) == []


def test_scan_values_right_rejects_non_callable():
    with pytest.raises(TypeError):
        scan_values_right([1], 0, 1)


def test_scan_values_right_public_api():
    assert get("scan_values_right") is not None
    assert "scan_values_right" in signatures()
    assert any(entry["name"] == "scan_values_right" for entry in entries())
