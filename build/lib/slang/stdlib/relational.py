from __future__ import annotations


def _validate_records(records, name: str) -> None:
    if not isinstance(records, list) or not all(isinstance(row, dict) for row in records):
        raise TypeError(f"{name} expects List<Record>")


def distinct_by(records: list[dict], key: str) -> list[dict]:
    """Keep the first record for each distinct value of key, preserving order."""
    _validate_records(records, "distinct_by")
    if not isinstance(key, str):
        raise TypeError("distinct_by expects a Text key")
    seen = set()
    result = []
    for row in records:
        value = row.get(key)
        try:
            marker = (type(value), value)
            hash(marker)
        except TypeError:
            marker = (type(value), repr(value))
        if marker not in seen:
            seen.add(marker)
            result.append(dict(row))
    return result


def join_records(left: list[dict], right: list[dict], left_key: str, right_key: str) -> list[dict]:
    """Perform a deterministic inner join, merging matching records left-to-right."""
    _validate_records(left, "join_records")
    _validate_records(right, "join_records")
    if not isinstance(left_key, str) or not isinstance(right_key, str):
        raise TypeError("join_records expects Text key names")

    index = {}
    for row in right:
        value = row.get(right_key)
        try:
            marker = (type(value), value)
            hash(marker)
        except TypeError:
            marker = (type(value), repr(value))
        index.setdefault(marker, []).append(row)

    result = []
    for lrow in left:
        value = lrow.get(left_key)
        try:
            marker = (type(value), value)
            hash(marker)
        except TypeError:
            marker = (type(value), repr(value))
        for rrow in index.get(marker, []):
            merged = dict(lrow)
            merged.update(rrow)
            result.append(merged)
    return result


def partition(records: list[dict], key: str, value) -> dict:
    """Split records into matching and remaining rows by a field value."""
    _validate_records(records, "partition")
    if not isinstance(key, str):
        raise TypeError("partition expects a Text key")
    matching = []
    rest = []
    for row in records:
        if row.get(key) == value:
            matching.append(dict(row))
        else:
            rest.append(dict(row))
    return {"matching": matching, "rest": rest}


def order_by(records: list[dict], key: str, descending: bool = False) -> list[dict]:
    """Sort records by a field while preserving stable order for equal values."""
    _validate_records(records, "order_by")
    if not isinstance(key, str):
        raise TypeError("order_by expects a Text key")
    if not isinstance(descending, bool):
        raise TypeError("order_by expects a Boolean direction")
    values = [row.get(key) for row in records]
    try:
        ordered = sorted(records, key=lambda row: row.get(key), reverse=descending)
    except TypeError as exc:
        raise TypeError("order_by field values must be mutually orderable") from exc
    return [dict(row) for row in ordered]


def find_by(records: list[dict], key: str, value):
    """Return the first record whose field equals value, or None when absent."""
    _validate_records(records, "find_by")
    if not isinstance(key, str):
        raise TypeError("find_by expects a Text key")
    for row in records:
        if row.get(key) == value:
            return dict(row)
    return None


def count_by(records: list[dict], key: str, value) -> int:
    """Count records whose field equals value."""
    _validate_records(records, "count_by")
    if not isinstance(key, str):
        raise TypeError("count_by expects a Text key")
    return sum(1 for row in records if row.get(key) == value)
