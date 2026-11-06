"""LSP symbol and definition navigation for S-Lang."""
from __future__ import annotations

from dataclasses import is_dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import quote

from .ast import source_span_of


def _lsp_range(span):
    if span is None:
        return None
    start = span.start
    end = span.end or span.start
    return {
        "start": {"line": max(start.line - 1, 0), "character": max(start.column - 1, 0)},
        "end": {"line": max(end.line - 1, 0), "character": max(end.column - 1, 0)},
    }


def _kind(decl) -> int:
    name = type(decl).__name__
    return {
        "FunctionDecl": 12, "PropertyDecl": 12, "EntityDecl": 5,
        "RecordDecl": 23, "DataDecl": 13, "BodyDecl": 5,
        "CircleDecl": 5, "GraphDecl": 5, "BindingDecl": 13,
        "StateDecl": 13, "ModuleDecl": 2,
    }.get(name, 13)


def _decl_name(decl):
    return getattr(decl, "name", None)


def _top_level_declarations(module):
    fields = (
        "module", "functions", "properties", "entities", "records", "datasets",
        "bodies", "circles", "graphs", "bindings", "states",
    )
    for field in fields:
        value = getattr(module, field, None)
        if value is None:
            continue
        items = value if isinstance(value, (list, tuple)) else (value,)
        for decl in items:
            if decl is not None and _decl_name(decl):
                yield decl


def document_symbols(program):
    """Return LSP DocumentSymbol entries for top-level AST declarations."""
    result = []
    module = getattr(program, "ast", None)
    if module is None:
        return ()
    for decl in _top_level_declarations(module):
        span = source_span_of(decl)
        rng = _lsp_range(span)
        if rng is None:
            continue
        name = _decl_name(decl)
        result.append({
            "name": name,
            "kind": _kind(decl),
            "range": rng,
            "selectionRange": rng,
        })
    result.sort(key=lambda item: (item["range"]["start"]["line"], item["range"]["start"]["character"], item["name"]))
    return tuple(result)


def symbol_information(uri: str, program):
    """Return legacy WorkspaceSymbol-style SymbolInformation entries."""
    path = Path(uri.replace("file://", "")) if uri.startswith("file://") else None
    container = path.name if path else None
    result = []
    for symbol in document_symbols(program):
        entry = {
            "name": symbol["name"],
            "kind": symbol["kind"],
            "location": {"uri": uri, "range": symbol["range"]},
        }
        if container:
            entry["containerName"] = container
        result.append(entry)
    return tuple(result)


def definition_candidates(program, word: str):
    module = getattr(program, "ast", None)
    if module is None:
        return ()
    result = []
    for decl in _top_level_declarations(module):
        if _decl_name(decl) == word and source_span_of(decl) is not None:
            result.append(decl)
    return tuple(result)


def iter_name_nodes(value):
    """Yield named AST references (Name and Call) in deterministic order."""
    from .ast import Name, Call
    seen = set()
    def walk(item):
        if item is None or id(item) in seen:
            return
        if isinstance(item, Name):
            seen.add(id(item))
            yield item
            return
        if isinstance(item, Call):
            seen.add(id(item))
            yield Name(item.name)
            return
        if is_dataclass(item):
            seen.add(id(item))
            for field_name in item.__dataclass_fields__:
                yield from walk(getattr(item, field_name))
        elif isinstance(item, (list, tuple)):
            for child in item:
                yield from walk(child)
        elif isinstance(item, dict):
            for key in sorted(item, key=lambda x: str(x)):
                yield from walk(item[key])
    yield from walk(value)


def names_at_position(program, line: int, character: int):
    for node in iter_name_nodes(program.ast):
        span = source_span_of(node)
        if span is None:
            continue
        start = span.start
        end = span.end or start
        if line + 1 < start.line or line + 1 > end.line:
            continue
        if start.line == end.line and not (start.column - 1 <= character <= end.column - 1):
            continue
        yield node.name


def references(program, word: str):
    result = []
    for node in iter_name_nodes(program.ast):
        if node.name != word:
            continue
        span = source_span_of(node)
        if span is not None:
            result.append(span)
    return tuple(result)


def named_references(value):
    """Yield (name, source span) pairs for identifiers and calls."""
    from .ast import Name, Call
    seen = set()
    def walk(item):
        if item is None or id(item) in seen:
            return
        if isinstance(item, Name):
            seen.add(id(item))
            span = source_span_of(item)
            if span is not None:
                yield item.name, span
            return
        if isinstance(item, Call):
            seen.add(id(item))
            span = source_span_of(item)
            if span is not None:
                yield item.name, span
            for arg in item.args:
                yield from walk(arg)
            return
        if is_dataclass(item):
            seen.add(id(item))
            for field_name in item.__dataclass_fields__:
                yield from walk(getattr(item, field_name))
        elif isinstance(item, (list, tuple)):
            for child in item:
                yield from walk(child)
        elif isinstance(item, dict):
            for key in sorted(item, key=lambda x: str(x)):
                yield from walk(item[key])
    yield from walk(value)


def named_at_position(program, line: int, character: int):
    for name, span in named_references(program.ast):
        start = span.start
        end = span.end or start
        if line + 1 < start.line or line + 1 > end.line:
            continue
        if start.line == end.line and not (start.column - 1 <= character <= end.column - 1):
            continue
        yield name


def named_reference_spans(program, word: str):
    return tuple(span for name, span in named_references(program.ast) if name == word)
