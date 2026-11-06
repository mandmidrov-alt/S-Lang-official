import pytest

from slang.stdlib.datetime import (
    add_days_datetime,
    add_seconds_datetime,
    diff_seconds_datetime,
    format_datetime,
    parse_datetime,
    weekday_datetime,
    week_number_datetime,
)


def test_iso_parser_explains_invalid_calendar_date():
    with pytest.raises(ValueError, match="invalid ISO-8601 datetime") as error:
        parse_datetime("2026-02-30T12:00:00Z")
    assert "2026-10-29T14:30:00Z" in str(error.value)


def test_custom_format_mismatch_names_value_and_format():
    with pytest.raises(ValueError, match="does not match format") as error:
        parse_datetime("29/10/2026", "%Y-%m-%d")
    assert "%Y-%m-%d" in str(error.value)


def test_non_text_datetime_is_reported_as_type_error():
    with pytest.raises(TypeError, match="expects Text datetime"):
        format_datetime(20261029, "%Y-%m-%d")


def test_format_datetime_reports_invalid_iso_input_consistently():
    with pytest.raises(ValueError, match="format_datetime: invalid ISO-8601 datetime"):
        format_datetime("not-a-date", "%Y")


def test_calendar_helpers_use_the_same_input_diagnostics():
    for helper in (weekday_datetime, week_number_datetime):
        with pytest.raises(ValueError, match="invalid ISO-8601 datetime"):
            helper("2026-13-01T00:00:00")


def test_arithmetic_overflow_explains_supported_range():
    with pytest.raises(ValueError, match="outside the supported datetime range"):
        add_seconds_datetime("9999-12-31T23:59:59", 1)
    with pytest.raises(ValueError, match="outside the supported datetime range"):
        add_days_datetime("9999-12-31T23:59:59", 1)


def test_timezone_awareness_mismatch_remains_explicit():
    with pytest.raises(ValueError, match="both datetimes to be timezone-aware or both naive"):
        diff_seconds_datetime("2026-10-29T00:00:00", "2026-10-29T00:00:00Z")


def test_parse_datetime_rejects_non_text_format_even_when_falsy():
    with pytest.raises(TypeError, match="expects Text format"):
        parse_datetime("2026-10-29T14:30:00Z", 0)
