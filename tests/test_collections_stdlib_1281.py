import pytest

from slang.stdlib import scan_values
from slang.stdlib.catalog import entries
from slang.stdlib.registry import get, signatures


def test_scan_values_returns_intermediate_results():
    assert scan_values([1, 2, 3, 4], 0, lambda total, value: total + value) == [1, 3, 6, 10]


def test_scan_values_uses_initial_only_as_seed():
    values = [2, 3]
    assert scan_values(values, 10, lambda total, value: total + value) == [12, 15]
    assert values == [2, 3]


def test_scan_values_empty_returns_empty():
    assert scan_values([], 42, lambda total, value: total + value) == []


def test_scan_values_rejects_non_callable():
    with pytest.raises(TypeError):
        scan_values([1], 0, 1)


def test_scan_values_public_api():
    assert get("scan_values") is not None
    assert "scan_values" in signatures()
    assert any(entry["name"] == "scan_values" for entry in entries())
