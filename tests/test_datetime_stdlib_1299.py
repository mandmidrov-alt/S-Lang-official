from slang.stdlib.datetime import is_leap_year, days_in_month, weekday_datetime, week_number_datetime
from slang.stdlib import is_leap_year as public_is_leap_year, days_in_month as public_days_in_month
from slang.stdlib.registry import get, signatures
from slang.stdlib.catalog import entries


def test_leap_year_rules():
    assert is_leap_year(2024) is True
    assert is_leap_year(2025) is False
    assert is_leap_year(1900) is False
    assert is_leap_year(2000) is True


def test_days_in_month():
    assert days_in_month(2026, 2) == 28
    assert days_in_month(2024, 2) == 29
    assert days_in_month(2026, 4) == 30
    assert days_in_month(2026, 12) == 31


def test_weekday_and_iso_week():
    assert weekday_datetime("2026-09-27T12:00:00Z") == 7
    assert weekday_datetime("2026-09-28T12:00:00Z") == 1
    assert week_number_datetime("2026-01-01T00:00:00Z") == 1
    assert week_number_datetime("2026-09-27T12:00:00Z") == 39


def test_public_registry_catalog():
    assert public_is_leap_year(2024) is True
    assert public_days_in_month(2024, 2) == 29
    assert get("weekday_datetime") is not None
    assert "week_number_datetime" in signatures()
    names = {entry["name"] for entry in entries()}
    assert {"is_leap_year", "days_in_month", "weekday_datetime", "week_number_datetime"} <= names
