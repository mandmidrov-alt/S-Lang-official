"""LSP inlay-hint helpers for S-Lang.

The first inlay-hint layer exposes parameter names at call sites.  It is
purely semantic: only functions visible in the current document's public
workspace view are annotated, and hints are derived from declaration order.
"""
from __future__ import annotations

from dataclasses import fields as dataclass_fields, is_dataclass
from typing import Iterable, Mapping

from .ast import Call, FunctionDecl, source_span_of


def _walk(value, _seen=None):
    if _seen is None:
        _seen = set()
    if isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk(item, _seen)
        return
    if isinstance(value, Mapping):
        for item in value.values():
            yield from _walk(item, _seen)
        return
    if not is_dataclass(value):
        return
    marker = id(value)
    if marker in _seen:
        return
    _seen.add(marker)
    yield value
    for field in dataclass_fields(value):
        child = getattr(value, field.name)
        if is_dataclass(child) or isinstance(child, (list, tuple, dict)):
            yield from _walk(child, _seen)


def _function_parameters(programs: Iterable[object]) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    for program in programs:
        for decl in getattr(program.ast, "functions", ()):
            if isinstance(decl, FunctionDecl):
                result.setdefault(decl.name, tuple(name for name, _ in decl.parameters))
    return result


def _inside(position: dict, start: dict, end: dict) -> bool:
    return (start["line"], start["character"]) <= (position["line"], position["character"]) < (end["line"], end["character"])


def inlay_hints(program, related_programs: Iterable[object], text: str, *, range_start: dict | None = None, range_end: dict | None = None) -> tuple[dict, ...]:
    signatures = _function_parameters((program, *tuple(related_programs)))
    if not signatures:
        return ()
    result: list[dict] = []
    for node in _walk(program.ast):
        if not isinstance(node, Call):
            continue
        parameters = signatures.get(node.name)
        if not parameters:
            continue
        for index, (argument, parameter) in enumerate(zip(node.args, parameters)):
            span = source_span_of(argument)
            if span is None:
                continue
            end = span.end or span.start
            start = {"line": span.start.line - 1, "character": span.start.column - 1}
            finish = {"line": end.line - 1, "character": end.column - 1}
            if range_start is not None and (finish["line"], finish["character"]) <= (range_start["line"], range_start["character"]):
                continue
            if range_end is not None and (start["line"], start["character"]) >= (range_end["line"], range_end["character"]):
                continue
            result.append({
                "position": start,
                "label": f"{parameter}: ",
                "kind": 2,
                "paddingRight": False,
            })
    result.sort(key=lambda item: (item["position"]["line"], item["position"]["character"], item["label"]))
    return tuple(result)
