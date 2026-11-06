from __future__ import annotations


def _validate_records(records, name: str) -> None:
    if not isinstance(records, list) or not all(isinstance(row, dict) for row in records):
        raise TypeError(f"{name} expects List<Record>")


def _validate_key(key, name: str) -> None:
    if not isinstance(key, str):
        raise TypeError(f"{name} expects a Text key")


def window(records: list[dict], size: int, step: int = 1) -> list[list[dict]]:
    """Create deterministic overlapping windows of records."""
    _validate_records(records, "window")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise ValueError("window size must be a positive Number")
    if not isinstance(step, int) or isinstance(step, bool) or step <= 0:
        raise ValueError("window step must be a positive Number")
    return [[dict(row) for row in records[i:i + size]]
            for i in range(0, len(records), step)
            if len(records[i:i + size]) == size]


def rank_by(records: list[dict], key: str, descending: bool = False) -> list[dict]:
    """Add a 1-based competition rank while preserving input order for ties."""
    _validate_records(records, "rank_by")
    _validate_key(key, "rank_by")
    if not isinstance(descending, bool):
        raise TypeError("rank_by expects a Boolean direction")
    try:
        indexed = list(enumerate(records))
        ordered = sorted(indexed, key=lambda item: item[1].get(key), reverse=descending)
    except TypeError as exc:
        raise TypeError("rank_by field values must be mutually orderable") from exc
    result = [dict(row) for row in records]
    previous = object()
    rank = 0
    for position, (original_index, row) in enumerate(ordered, start=1):
        value = row.get(key)
        if position == 1 or value != previous:
            rank = position
            previous = value
        result[original_index]["rank"] = rank
    return result


def top_by(records: list[dict], key: str, count: int) -> list[dict]:
    """Return up to count records with the largest values of key."""
    _validate_records(records, "top_by")
    _validate_key(key, "top_by")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise ValueError("top_by count must be a non-negative Number")
    try:
        ordered = sorted(enumerate(records), key=lambda item: item[1].get(key), reverse=True)
    except TypeError as exc:
        raise TypeError("top_by field values must be mutually orderable") from exc
    return [dict(row) for _, row in ordered[:count]]


def bottom_by(records: list[dict], key: str, count: int) -> list[dict]:
    """Return up to count records with the smallest values of key."""
    _validate_records(records, "bottom_by")
    _validate_key(key, "bottom_by")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise ValueError("bottom_by count must be a non-negative Number")
    try:
        ordered = sorted(enumerate(records), key=lambda item: item[1].get(key))
    except TypeError as exc:
        raise TypeError("bottom_by field values must be mutually orderable") from exc
    return [dict(row) for _, row in ordered[:count]]


def _numeric_values(rows: list[dict], key: str, name: str) -> list[float]:
    values = [row.get(key) for row in rows]
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        raise TypeError(f"{name} value field must contain Number values")
    return values


def window_sum(records: list[dict], value_key: str, size: int, step: int = 1) -> list[dict]:
    """Return deterministic rolling sums over complete windows."""
    _validate_records(records, "window_sum")
    _validate_key(value_key, "window_sum")
    windows = window(records, size, step)
    return [{"start": i * step, "sum": sum(_numeric_values(rows, value_key, "window_sum"))}
            for i, rows in enumerate(windows)]


def window_average(records: list[dict], value_key: str, size: int, step: int = 1) -> list[dict]:
    """Return deterministic rolling averages over complete windows."""
    _validate_records(records, "window_average")
    _validate_key(value_key, "window_average")
    windows = window(records, size, step)
    result = []
    for i, rows in enumerate(windows):
        values = _numeric_values(rows, value_key, "window_average")
        result.append({"start": i * step, "average": sum(values) / len(values)})
    return result


def group_top_by(records: list[dict], group_key: str, value_key: str, count: int) -> list[dict]:
    """Return the top records independently inside each group."""
    _validate_records(records, "group_top_by")
    _validate_key(group_key, "group_top_by")
    _validate_key(value_key, "group_top_by")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise ValueError("group_top_by count must be a non-negative Number")
    result = []
    groups = {}
    order = []
    for row in records:
        marker = (type(row.get(group_key)), row.get(group_key))
        try:
            hash(marker)
        except TypeError:
            marker = (type(row.get(group_key)), repr(row.get(group_key)))
        if marker not in groups:
            groups[marker] = []
            order.append(marker)
        groups[marker].append(row)
    for marker in order:
        rows = groups[marker]
        try:
            ordered = sorted(enumerate(rows), key=lambda item: item[1].get(value_key), reverse=True)
        except TypeError as exc:
            raise TypeError("group_top_by field values must be mutually orderable") from exc
        result.extend(dict(row) for _, row in ordered[:count])
    return result
