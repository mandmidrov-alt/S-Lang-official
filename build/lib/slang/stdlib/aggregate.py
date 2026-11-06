from __future__ import annotations


def _validate_records(records):
    if not isinstance(records, list) or not all(isinstance(row, dict) for row in records):
        raise TypeError("aggregate operation expects List<Record>")


def _groups(records: list[dict], key: str):
    _validate_records(records)
    if not isinstance(key, str):
        raise TypeError("group key expects Text")
    groups = {}
    order = []
    for row in records:
        value = row.get(key)
        try:
            marker = (type(value), value)
            hash(marker)
        except TypeError:
            marker = (type(value), repr(value))
        if marker not in groups:
            groups[marker] = {"key": value, "items": []}
            order.append(marker)
        groups[marker]["items"].append(row)
    return [groups[marker] for marker in order]


def group_by(records: list[dict], key: str) -> list[dict]:
    """Group records by a field, preserving first-seen group order."""
    return _groups(records, key)


def group_count(records: list[dict], key: str) -> list[dict]:
    """Return one summary record per group with its row count."""
    return [{"key": group["key"], "count": len(group["items"])} for group in _groups(records, key)]


def group_sum(records: list[dict], group_key: str, value_key: str) -> list[dict]:
    """Sum a numeric field independently inside each group."""
    groups = _groups(records, group_key)
    result = []
    for group in groups:
        values = [row.get(value_key) for row in group["items"]]
        if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
            raise TypeError("group_sum value field must contain Number values")
        result.append({"key": group["key"], "sum": sum(values)})
    return result


def group_min(records: list[dict], group_key: str, value_key: str) -> list[dict]:
    """Minimum numeric value independently inside each group."""
    groups = _groups(records, group_key)
    result = []
    for group in groups:
        values = [row.get(value_key) for row in group["items"]]
        if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
            raise TypeError("group_min value field must contain Number values")
        result.append({"key": group["key"], "min": min(values)})
    return result


def group_max(records: list[dict], group_key: str, value_key: str) -> list[dict]:
    """Maximum numeric value independently inside each group."""
    groups = _groups(records, group_key)
    result = []
    for group in groups:
        values = [row.get(value_key) for row in group["items"]]
        if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
            raise TypeError("group_max value field must contain Number values")
        result.append({"key": group["key"], "max": max(values)})
    return result


def group_average(records: list[dict], group_key: str, value_key: str) -> list[dict]:
    """Average a numeric field independently inside each group."""
    groups = _groups(records, group_key)
    result = []
    for group in groups:
        values = [row.get(value_key) for row in group["items"]]
        if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
            raise TypeError("group_average value field must contain Number values")
        result.append({"key": group["key"], "average": sum(values) / len(values)})
    return result


def frequency(values: list) -> list[dict]:
    """Return stable frequency records for a scalar collection.

    Each distinct value is represented once as ``{"value": ..., "count": ...}``.
    First-seen value order is preserved and equality remains type-sensitive.
    """
    if not isinstance(values, list):
        raise TypeError("frequency expects List")
    groups = {}
    order = []
    for value in values:
        try:
            marker = (type(value), value)
            hash(marker)
        except TypeError:
            marker = (type(value), repr(value))
        if marker not in groups:
            groups[marker] = {"value": value, "count": 0}
            order.append(marker)
        groups[marker]["count"] += 1
    return [groups[marker] for marker in order]

def mode(values: list):
    """Return the most frequent scalar value, breaking ties by first occurrence.

    Empty collections use the language runtime's explicit empty-value convention
    rather than fabricating a scalar.
    """
    if not isinstance(values, list):
        raise TypeError("mode expects List")
    if not values:
        return None
    rows = frequency(values)
    best = rows[0]
    for row in rows[1:]:
        if row["count"] > best["count"]:
            best = row
    return best["value"]

