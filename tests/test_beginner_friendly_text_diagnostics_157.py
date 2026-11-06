import pytest

from slang.stdlib.text import (
    char_at_text, count_text, join_texts, repeat_text, split, substring_text,
)


def test_split_empty_separator_explains_how_to_fix():
    with pytest.raises(ValueError, match="separator cannot be empty"):
        split("a,b", "")


def test_split_valid_input_is_unchanged():
    assert split("red,green,blue", ",") == ["red", "green", "blue"]
    assert split("", ",") == [""]


def test_join_texts_identifies_invalid_item_position():
    with pytest.raises(TypeError, match=r"item 1 must be Text"):
        join_texts(["first", 2, "third"], ",")


def test_join_texts_explains_separator_type():
    with pytest.raises(TypeError, match="Text separator"):
        join_texts(["a", "b"], 2)


def test_substring_text_explains_index_rules():
    with pytest.raises(ValueError, match="indices start at 0"):
        substring_text("hello", -1, 2)
    with pytest.raises(ValueError, match="end index cannot be smaller"):
        substring_text("hello", 3, 2)


def test_char_at_text_reports_valid_index_range():
    with pytest.raises(ValueError, match=r"valid indices are 0 through 2"):
        char_at_text("abc", 3)
    assert char_at_text("abc", 0) == "a"


def test_repeat_text_explains_negative_count():
    with pytest.raises(ValueError, match="zero or a positive number"):
        repeat_text("x", -1)
    assert repeat_text("x", 0) == ""


def test_count_text_explains_empty_search_term():
    with pytest.raises(ValueError, match="search term cannot be empty"):
        count_text("abc", "")
    assert count_text("banana", "na") == 2.0
