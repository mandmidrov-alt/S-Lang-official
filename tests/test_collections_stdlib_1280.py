import pytest

from slang.stdlib import fold_values
from slang.stdlib.catalog import entries
from slang.stdlib.registry import get, signatures


def test_fold_values_accumulates_left_to_right():
    assert fold_values([1, 2, 3, 4], 0, lambda total, value: total + value) == 10


def test_fold_values_supports_non_numeric_accumulators():
    assert fold_values(["b", "c"], "a", lambda text, value: text + value) == "abc"


def test_fold_values_empty_collection_returns_initial():
    assert fold_values([], 42, lambda total, value: total + value) == 42


def test_fold_values_rejects_invalid_combine():
    with pytest.raises(TypeError, match="callable combine"):
        fold_values([1], 0, "not_callable")


def test_fold_values_public_api():
    assert get("fold_values") is not None
    assert "fold_values" in signatures()
    assert any(entry["name"] == "fold_values" for entry in entries())
