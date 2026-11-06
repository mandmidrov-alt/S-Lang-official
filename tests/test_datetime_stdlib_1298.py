from slang.stdlib.datetime import (
    add_days_datetime, add_months_datetime, start_of_day_datetime,
    end_of_day_datetime, date_components_datetime,
)
from slang.stdlib import add_days_datetime as public_add_days_datetime
from slang.stdlib.registry import get, signatures
from slang.stdlib.catalog import entries


def test_add_days():
    assert add_days_datetime("2026-09-27T12:00:00Z", 2) == "2026-09-29T12:00:00Z"
    assert add_days_datetime("2026-09-27T12:00:00", -1) == "2026-09-26T12:00:00"


def test_add_months_clamps_month_end():
    assert add_months_datetime("2026-01-31T12:30:00Z", 1) == "2026-02-28T12:30:00Z"
    assert add_months_datetime("2024-01-31T12:30:00Z", 1) == "2024-02-29T12:30:00Z"
    assert add_months_datetime("2026-03-31T12:30:00Z", -1) == "2026-02-28T12:30:00Z"


def test_day_boundaries():
    value = "2026-09-27T12:34:56Z"
    assert start_of_day_datetime(value) == "2026-09-27T00:00:00Z"
    assert end_of_day_datetime(value) == "2026-09-27T23:59:59Z"


def test_components():
    assert date_components_datetime("2026-09-27T12:34:56Z") == [2026, 9, 27, 12, 34, 56]


def test_public_registry_catalog():
    assert public_add_days_datetime("2026-09-27T00:00:00Z", 1) == "2026-09-28T00:00:00Z"
    assert get("add_months_datetime") is not None
    assert "date_components_datetime" in signatures()
    names = {entry["name"] for entry in entries()}
    assert {"add_days_datetime", "add_months_datetime", "start_of_day_datetime", "end_of_day_datetime", "date_components_datetime"} <= names
