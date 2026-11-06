from datetime import datetime

from slang.stdlib.datetime import (
    now_utc, today_utc, parse_datetime, format_datetime,
    add_seconds_datetime, diff_seconds_datetime,
)
from slang.stdlib import parse_datetime as public_parse_datetime
from slang.stdlib.registry import get, signatures
from slang.stdlib.catalog import entries


def test_now_and_today():
    assert now_utc().endswith("Z")
    datetime.fromisoformat(now_utc().replace("Z", "+00:00"))
    assert len(today_utc()) == 10


def test_parse_and_format():
    value = parse_datetime("2026-09-27T12:00:00Z", "")
    assert value == "2026-09-27T12:00:00Z"
    assert format_datetime(value, "%Y-%m-%d") == "2026-09-27"


def test_add_and_diff():
    base = "2026-09-27T12:00:00Z"
    later = add_seconds_datetime(base, 3600)
    assert later == "2026-09-27T13:00:00Z"
    assert diff_seconds_datetime(base, later) == 3600


def test_naive_datetime_roundtrip():
    value = parse_datetime("2026-09-27 12:30:00", "%Y-%m-%d %H:%M:%S")
    assert value == "2026-09-27T12:30:00"
    assert format_datetime(value, "%H:%M") == "12:30"


def test_public_api_registry_catalog():
    assert public_parse_datetime("2026-09-27T00:00:00Z", "") == "2026-09-27T00:00:00Z"
    assert get("parse_datetime") is not None
    assert "diff_seconds_datetime" in signatures()
    assert any(e["name"] == "now_utc" for e in entries())
