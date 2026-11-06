import pytest
from slang.stdlib.text import pad_left_text, pad_right_text

@pytest.mark.parametrize(("value", "width", "fill", "expected"), [
    ("x", 5, "0", "0000x"),
    ("x", 5, "ab", "ababx"),
    ("x", 4, "ab", "abax"),
    ("hello", 3, "0", "hello"),
    ("", 3, "xy", "xyx"),
])
def test_pad_left_fills_exact_requested_width(value, width, fill, expected):
    assert pad_left_text(value, width, fill) == expected

@pytest.mark.parametrize(("value", "width", "fill", "expected"), [
    ("x", 5, "0", "x0000"),
    ("x", 5, "ab", "xabab"),
    ("x", 4, "ab", "xaba"),
    ("hello", 3, "0", "hello"),
    ("", 3, "xy", "xyx"),
])
def test_pad_right_fills_exact_requested_width(value, width, fill, expected):
    assert pad_right_text(value, width, fill) == expected

def test_padding_rejects_empty_fill():
    with pytest.raises(ValueError, match="fill cannot be empty"):
        pad_left_text("x", 3, "")
    with pytest.raises(ValueError, match="fill cannot be empty"):
        pad_right_text("x", 3, "")
