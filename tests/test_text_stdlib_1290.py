from slang.stdlib import join_lines, normalize_whitespace, split_lines
from slang.stdlib.catalog import entries
from slang.stdlib.registry import get, signatures
import pytest


def test_normalize_whitespace_collapses_and_trims():
    assert normalize_whitespace("  alpha\t beta\n gamma  ") == "alpha beta gamma"


def test_split_lines_accepts_common_line_endings():
    assert split_lines("a\r\nb\nc\rd") == ["a", "b", "c", "d"]


def test_join_lines_is_inverse_for_logical_lines():
    assert join_lines(["a", "b", "c"]) == "a\nb\nc"


def test_join_lines_rejects_non_text_values():
    with pytest.raises(TypeError):
        join_lines(["a", 2])


def test_public_api_registry_and_catalog():
    assert get("normalize_whitespace") is not None
    assert get("split_lines") is not None
    assert get("join_lines") is not None
    sigs = signatures()
    assert "normalize_whitespace" in sigs
    assert "split_lines" in sigs
    assert "join_lines" in sigs
    names = {entry["name"] for entry in entries()}
    assert {"normalize_whitespace", "split_lines", "join_lines"} <= names
