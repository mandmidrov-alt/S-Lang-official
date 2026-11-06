from __future__ import annotations


def trim(value: str) -> str:
    return value.strip()


def lower(value: str) -> str:
    return value.lower()


def upper(value: str) -> str:
    return value.upper()


def starts_with(value: str, prefix: str) -> bool:
    return value.startswith(prefix)


def ends_with(value: str, suffix: str) -> bool:
    return value.endswith(suffix)


def replace(value: str, old: str, new: str) -> str:
    return value.replace(old, new)


def split(value: str, separator: str) -> list[str]:
    if not isinstance(value, str) or not isinstance(separator, str):
        raise TypeError("split expects Text and Text; check the input text and separator")
    if separator == "":
        raise ValueError("split separator cannot be empty; provide a character or text separator")
    return value.split(separator)


def contains_text(value: str, needle: str) -> bool:
    return needle in value


def index_of(value: str, needle: str) -> float:
    return value.find(needle)


def join_texts(values: list[str], separator: str) -> str:
    if not isinstance(values, list):
        raise TypeError("join_texts expects List<Text> as its first argument")
    if not isinstance(separator, str):
        raise TypeError("join_texts expects a Text separator as its second argument")
    for index, value in enumerate(values):
        if not isinstance(value, str):
            raise TypeError(f"join_texts item {index} must be Text, but received {type(value).__name__}")
    return separator.join(values)


def repeat_text(value: str, count: float) -> str:
    if not isinstance(value, str):
        raise TypeError("repeat_text expects Text as its first argument")
    if isinstance(count, bool) or not isinstance(count, (int, float)):
        raise TypeError("repeat_text expects a Number count as its second argument")
    count = int(count)
    if count < 0:
        raise ValueError("repeat_text count cannot be negative; use zero or a positive number")
    return value * count


def length_text(value: str) -> float:
    return float(len(value))


def substring_text(value: str, start: float, end: float) -> str:
    if not isinstance(value, str):
        raise TypeError("substring_text expects Text as its first argument")
    if any(isinstance(index, bool) or not isinstance(index, (int, float)) for index in (start, end)):
        raise TypeError("substring_text start and end indices must be Numbers")
    start_i, end_i = int(start), int(end)
    if start_i < 0 or end_i < 0:
        raise ValueError("substring_text indices cannot be negative; indices start at 0")
    if end_i < start_i:
        raise ValueError("substring_text end index cannot be smaller than start index")
    return value[start_i:end_i]


def char_at_text(value: str, index: float) -> str:
    if not isinstance(value, str):
        raise TypeError("char_at_text expects Text as its first argument")
    if isinstance(index, bool) or not isinstance(index, (int, float)):
        raise TypeError("char_at_text index must be a Number")
    index_i = int(index)
    if index_i < 0 or index_i >= len(value):
        raise ValueError(f"char_at_text index {index_i} is outside the text; valid indices are 0 through {len(value) - 1}")
    return value[index_i]


def pad_left_text(value: str, width: float, fill: str) -> str:
    if not fill:
        raise ValueError("pad_left_text fill cannot be empty")
    width_i = int(width)
    if width_i < 0:
        raise ValueError("pad_left_text width cannot be negative")
    if len(value) >= width_i:
        return value
    padding = width_i - len(value)
    return (fill * ((padding + len(fill) - 1) // len(fill)))[:padding] + value


def pad_right_text(value: str, width: float, fill: str) -> str:
    if not fill:
        raise ValueError("pad_right_text fill cannot be empty")
    width_i = int(width)
    if width_i < 0:
        raise ValueError("pad_right_text width cannot be negative")
    if len(value) >= width_i:
        return value
    padding = width_i - len(value)
    return value + (fill * ((padding + len(fill) - 1) // len(fill)))[:padding]


def count_text(value: str, needle: str) -> float:
    """Count non-overlapping occurrences of ``needle`` in ``value``."""
    if not isinstance(value, str) or not isinstance(needle, str):
        raise TypeError("count_text expects Text to search and a Text search term")
    if needle == "":
        raise ValueError("count_text search term cannot be empty; provide at least one character")
    return float(value.count(needle))


def remove_prefix_text(value: str, prefix: str) -> str:
    if value.startswith(prefix):
        return value[len(prefix):]
    return value


def remove_suffix_text(value: str, suffix: str) -> str:
    if value.endswith(suffix):
        return value[:-len(suffix)] if suffix else value
    return value


def reverse_text(value: str) -> str:
    return value[::-1]


def normalize_whitespace(value: str) -> str:
    """Collapse runs of whitespace and trim surrounding whitespace."""
    return " ".join(value.split())


def split_lines(value: str) -> list[str]:
    """Split text into logical lines while accepting common line endings."""
    return value.splitlines()


def join_lines(values: list[str]) -> str:
    """Join text lines using the platform-independent newline separator."""
    if not all(isinstance(value, str) for value in values):
        raise TypeError("join_lines expects List<Text>")
    return "\n".join(values)
