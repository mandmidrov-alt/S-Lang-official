"""Public module-level organization of the S-Lang standard library.

The registry remains the source of callable contracts.  This layer gives the
library a stable public module taxonomy without changing existing function
names or execution semantics.
"""
from __future__ import annotations

from .catalog import entries

MODULES = {
    "math": "numeric and mathematical operations",
    "text": "text normalization and matching",
    "collections": "generic collection operations",
    "data": "record and field operations",
    "aggregate": "grouped aggregation",
    "relational": "record joins and relational operations",
    "analytics": "windows, ranking, and top/bottom analysis",
    "json": "JSON parsing and serialization",
    "csv": "CSV input and output",
    "path": "path manipulation",
    "files": "filesystem inspection and mutation",
    "process": "process context and external program execution",
    "datetime": "date and time parsing, formatting, and calendar arithmetic",
}


def module_entries(name: str | None = None) -> list[dict]:
    rows = entries()
    if name is not None:
        if name not in MODULES:
            raise KeyError(name)
        rows = [row for row in rows if row["module"] == f"slang.stdlib.{name}"]
    return rows


def modules() -> list[dict]:
    result = []
    for name in sorted(MODULES):
        rows = module_entries(name)
        result.append({
            "name": name,
            "module": f"slang.stdlib.{name}",
            "description": MODULES[name],
            "functions": [row["name"] for row in rows],
            "function_count": len(rows),
            "effects": sorted({row["effect"] for row in rows}),
        })
    return result
