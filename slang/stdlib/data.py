from __future__ import annotations


def keys(record: dict) -> list[str]:
    if not isinstance(record, dict):
        raise TypeError("keys expects Record")
    return list(record.keys())


def get(record: dict, key: str):
    if not isinstance(record, dict) or not isinstance(key, str):
        raise TypeError("get expects Record and Text key")
    return record.get(key)


def has(record: dict, key: str) -> bool:
    if not isinstance(record, dict) or not isinstance(key, str):
        raise TypeError("has expects Record and Text key")
    return key in record


def pluck(records: list[dict], key: str) -> list:
    if not isinstance(records, list) or not isinstance(key, str):
        raise TypeError("pluck expects List<Record> and Text key")
    if not all(isinstance(record, dict) for record in records):
        raise TypeError("pluck expects List<Record>")
    return [record.get(key) for record in records]


def select_fields(record: dict, fields: list[str]) -> dict:
    if not isinstance(record, dict) or not isinstance(fields, list):
        raise TypeError("select_fields expects Record and List<Text>")
    if not all(isinstance(field, str) for field in fields):
        raise TypeError("select_fields expects List<Text>")
    return {field: record[field] for field in fields if field in record}


def merge_records(left: dict, right: dict) -> dict:
    if not isinstance(left, dict) or not isinstance(right, dict):
        raise TypeError("merge_records expects two Records")
    result = dict(left)
    result.update(right)
    return result


def remove_field(record: dict, key: str) -> dict:
    if not isinstance(record, dict) or not isinstance(key, str):
        raise TypeError("remove_field expects Record and Text key")
    result = dict(record)
    result.pop(key, None)
    return result
