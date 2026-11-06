from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


class CSVDataError(ValueError):
    """A CSV file is readable as text but its table structure is invalid."""


def read_csv(path: str) -> list[dict[str, str]]:
    """Read a UTF-8 CSV file and report actionable table-shape errors."""
    try:
        with Path(path).open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle, strict=True)
            headers = next(reader, None)
            if headers is None:
                return []
            if not headers or all(not header.strip() for header in headers):
                raise CSVDataError("CSV header row is empty; add column names as the first row")
            blank = [str(index + 1) for index, header in enumerate(headers) if not header.strip()]
            if blank:
                raise CSVDataError(
                    "CSV header contains an empty column name at position " + ", ".join(blank)
                    + "; give every column a name"
                )
            seen: set[str] = set()
            duplicates: list[str] = []
            for header in headers:
                if header in seen and header not in duplicates:
                    duplicates.append(header)
                seen.add(header)
            if duplicates:
                raise CSVDataError(
                    "CSV header contains duplicate column name(s): " + ", ".join(repr(x) for x in duplicates)
                    + "; rename the columns so each header is unique"
                )

            rows: list[dict[str, str]] = []
            for values in reader:
                if not values:  # Match DictReader's treatment of completely blank lines.
                    continue
                line = reader.line_num
                if len(values) != len(headers):
                    if len(values) > len(headers):
                        detail = f"found {len(values) - len(headers)} extra field(s)"
                    else:
                        detail = f"missing {len(headers) - len(values)} field(s)"
                    raise CSVDataError(
                        f"CSV row at line {line} has {len(values)} field(s), but the header defines "
                        f"{len(headers)} column(s) ({detail}); check separators and quoted values"
                    )
                rows.append(dict(zip(headers, values)))
            return rows
    except csv.Error as exc:
        line = getattr(locals().get("reader"), "line_num", None)
        where = f" at line {line}" if line else ""
        raise CSVDataError(
            f"CSV syntax is invalid{where}: {exc}; check quotation marks, escaped quotes, and separators"
        ) from exc


def write_csv(path: str, rows: list[dict[str, Any]]) -> None:
    """Write row records as UTF-8 CSV using the first row's key order."""
    if not rows:
        Path(path).write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def csv_headers(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return []
    headers: list[str] = []
    for row in rows:
        for key in row:
            if key not in headers:
                headers.append(key)
    return headers
