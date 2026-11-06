from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _parse_iso_datetime(value: str, operation: str = "datetime operation") -> datetime:
    """Parse ISO-8601 input with a stable, actionable error message."""
    if not isinstance(value, str):
        raise TypeError(f"{operation} expects Text datetime; received {type(value).__name__}")
    raw = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(raw)
    except (ValueError, OverflowError) as exc:
        raise ValueError(
            f"{operation}: invalid ISO-8601 datetime {value!r}; use a valid date and time, "
            "for example '2026-10-29T14:30:00Z' or '2026-10-29T14:30:00'"
        ) from exc


def _parse_custom_datetime(value: str, format: str, operation: str) -> datetime:
    """Parse an explicitly formatted datetime and explain format mismatches."""
    if not isinstance(value, str):
        raise TypeError(f"{operation} expects Text datetime; received {type(value).__name__}")
    if not isinstance(format, str):
        raise TypeError(f"{operation} expects Text format; received {type(format).__name__}")
    try:
        return datetime.strptime(value, format)
    except (ValueError, OverflowError) as exc:
        raise ValueError(
            f"{operation}: datetime {value!r} does not match format {format!r}; "
            "check the format directives and that the date and time components are valid"
        ) from exc


def now_utc() -> str:
    """Return the current UTC instant as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def today_utc() -> str:
    """Return the current UTC calendar date as YYYY-MM-DD."""
    return datetime.now(timezone.utc).date().isoformat()


def parse_datetime(value: str, format: str = "") -> str:
    """Validate and normalize a datetime string to ISO-8601."""
    if not isinstance(format, str):
        raise TypeError(f"parse_datetime expects Text format; received {type(format).__name__}")
    if format:
        parsed = _parse_custom_datetime(value, format, "parse_datetime")
    else:
        parsed = _parse_iso_datetime(value, "parse_datetime")
    if parsed.tzinfo is None:
        return parsed.isoformat(timespec="seconds")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def format_datetime(value: str, format: str) -> str:
    """Format an ISO-8601 datetime using a strftime-style format."""
    if not isinstance(format, str):
        raise TypeError(f"format_datetime expects Text format; received {type(format).__name__}")
    parsed = _parse_iso_datetime(value, "format_datetime")
    try:
        return parsed.strftime(format)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"format_datetime: invalid format string {format!r}") from exc


def add_seconds_datetime(value: str, seconds: float) -> str:
    """Add seconds to an ISO-8601 datetime and return ISO-8601 text."""
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        raise TypeError("add_seconds_datetime expects Number seconds")
    parsed = _parse_iso_datetime(value, "add_seconds_datetime")
    try:
        result = parsed + timedelta(seconds=seconds)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"add_seconds_datetime: result is outside the supported datetime range for {seconds!r} seconds") from exc
    if result.tzinfo is not None:
        return result.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return result.isoformat(timespec="seconds")


def diff_seconds_datetime(first: str, second: str) -> float:
    """Return second-first in seconds for two ISO-8601 datetimes."""
    a = _parse_iso_datetime(first, "diff_seconds_datetime (first argument)")
    b = _parse_iso_datetime(second, "diff_seconds_datetime (second argument)")
    if (a.tzinfo is None) != (b.tzinfo is None):
        raise ValueError("diff_seconds_datetime requires both datetimes to be timezone-aware or both naive")
    return (b - a).total_seconds()


def add_days_datetime(value: str, days: float) -> str:
    """Add a whole number of calendar days to an ISO-8601 datetime."""
    if isinstance(days, bool) or not isinstance(days, (int, float)) or not float(days).is_integer():
        raise TypeError("add_days_datetime expects an integer Number of days")
    parsed = _parse_iso_datetime(value, "add_days_datetime")
    try:
        result = parsed + timedelta(days=int(days))
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"add_days_datetime: result is outside the supported datetime range for {int(days)} days") from exc
    if result.tzinfo is not None:
        return result.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return result.isoformat(timespec="seconds")


def add_months_datetime(value: str, months: float) -> str:
    """Add calendar months, clamping an overflowing day to month end."""
    if isinstance(months, bool) or not isinstance(months, (int, float)) or not float(months).is_integer():
        raise TypeError("add_months_datetime expects an integer Number of months")
    parsed = _parse_iso_datetime(value, "add_months_datetime")
    total = parsed.year * 12 + (parsed.month - 1) + int(months)
    year, month_index = divmod(total, 12)
    month = month_index + 1
    if year < 1 or year > 9999:
        raise ValueError("add_months_datetime result is outside supported datetime range")
    if month == 12:
        next_month = datetime(year + 1, 1, 1) if year < 9999 else None
    else:
        next_month = datetime(year, month + 1, 1)
    last_day = (next_month - timedelta(days=1)).day if next_month else 31
    day = min(parsed.day, last_day)
    result = parsed.replace(year=year, month=month, day=day)
    if result.tzinfo is not None:
        return result.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return result.isoformat(timespec="seconds")


def start_of_day_datetime(value: str) -> str:
    """Return the start of the calendar day for an ISO-8601 datetime."""
    parsed = _parse_iso_datetime(value, "start_of_day_datetime")
    result = parsed.replace(hour=0, minute=0, second=0, microsecond=0)
    if result.tzinfo is not None:
        return result.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return result.isoformat(timespec="seconds")


def end_of_day_datetime(value: str) -> str:
    """Return the final whole second of the calendar day."""
    parsed = _parse_iso_datetime(value, "end_of_day_datetime")
    result = parsed.replace(hour=23, minute=59, second=59, microsecond=0)
    if result.tzinfo is not None:
        return result.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return result.isoformat(timespec="seconds")


def date_components_datetime(value: str) -> list[float]:
    """Return year, month, day, hour, minute and second as numbers."""
    parsed = _parse_iso_datetime(value, "date_components_datetime")
    return [parsed.year, parsed.month, parsed.day, parsed.hour, parsed.minute, parsed.second]

def is_leap_year(year: float) -> bool:
    """Return whether a calendar year is a leap year in the Gregorian calendar."""
    if isinstance(year, bool) or not isinstance(year, (int, float)) or not float(year).is_integer():
        raise TypeError("is_leap_year expects an integer Number year")
    year = int(year)
    if year < 1 or year > 9999:
        raise ValueError("is_leap_year expects a year from 1 to 9999")
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def days_in_month(year: float, month: float) -> float:
    """Return the number of days in a Gregorian calendar month."""
    for value, name in ((year, "year"), (month, "month")):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not float(value).is_integer():
            raise TypeError(f"days_in_month expects integer Number {name}")
    year, month = int(year), int(month)
    if year < 1 or year > 9999:
        raise ValueError("days_in_month expects a year from 1 to 9999")
    if month < 1 or month > 12:
        raise ValueError("days_in_month expects month from 1 to 12")
    if month == 12:
        next_month = datetime(year + 1, 1, 1) if year < 9999 else None
    else:
        next_month = datetime(year, month + 1, 1)
    return float((next_month - timedelta(days=1)).day if next_month else 31)


def weekday_datetime(value: str) -> float:
    """Return ISO weekday number: Monday=1 through Sunday=7."""
    return float(_parse_iso_datetime(value, "weekday_datetime").isoweekday())


def week_number_datetime(value: str) -> float:
    """Return the ISO-8601 week number for a datetime."""
    return float(_parse_iso_datetime(value, "week_number_datetime").isocalendar().week)

