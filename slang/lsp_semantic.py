"""Semantic symbol resolution for S-Lang LSP navigation.

This layer deliberately uses the parsed AST and source spans rather than textual
matching.  It resolves local function scopes first and then workspace/imported
symbols, allowing rename and references to target one declaration only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .ast import (
    BindingDecl, FunctionDecl, LetOp, Name, Call, IfOp, ReturnOp,
    source_span_of,
)
from .lsp_navigation import _top_level_declarations, named_references


@dataclass(frozen=True)
class SemanticSymbol:
    name: str
    uri: str
    kind: str
    scope: str
    declaration: dict


def _range(span):
    if span is None:
        return None
    end = span.end or span.start
    return {"start": {"line": span.start.line - 1, "character": span.start.column - 1},
            "end": {"line": end.line - 1, "character": end.column - 1}}


def _word_range(text: str, span, name: str):
    rng = _range(span)
    if rng is None:
        return None
    lines = text.splitlines()
    line = span.start.line - 1
    if 0 <= line < len(lines):
        source = lines[line]
        start = max(0, span.start.column - 1)
        idx = source.find(name, start)
        if idx >= 0:
            return {"start": {"line": line, "character": idx},
                    "end": {"line": line, "character": idx + len(name)}}
    return rng


def _inside(span, line, character):
    if span is None:
        return False
    end = span.end or span.start
    p = (line + 1, character + 1)
    return (span.start.line, span.start.column) <= p <= (end.line, end.column)


def _body_statements(body):
    for stmt in body or ():
        yield stmt
        if isinstance(stmt, IfOp):
            yield from _body_statements(stmt.then_body)
            yield from _body_statements(stmt.else_body)


def _top_symbols(program, uri, text):
    result = []
    module = getattr(program, "ast", None)
    if module is None:
        return result
    for decl in _top_level_declarations(module):
        name = getattr(decl, "name", None)
        span = source_span_of(decl)
        if not name or span is None:
            continue
        result.append(SemanticSymbol(name, uri, type(decl).__name__, "module", {
            "uri": uri, "range": _word_range(text, span, name),
        }))
    return result


def _function_symbols(program, uri, text):
    result = []
    module = getattr(program, "ast", None)
    for fn in getattr(module, "functions", ()) or ():
        fn_span = source_span_of(fn)
        if fn_span is None:
            continue
        for name, _type in fn.parameters:
            # Parameters do not currently have individual AST spans. Locate them
            # within the function declaration header, which is stable source data.
            lines = text.splitlines()
            rng = None
            for ln in range(fn_span.start.line - 1, min(fn_span.end.line, len(lines))):
                source = lines[ln]
                idx = source.find(name)
                if idx >= 0:
                    rng = {"start": {"line": ln, "character": idx},
                           "end": {"line": ln, "character": idx + len(name)}}
                    break
            if rng:
                result.append(SemanticSymbol(name, uri, "Parameter", f"function:{fn.name}", {"uri": uri, "range": rng}))
        for stmt in _body_statements(fn.body):
            if isinstance(stmt, LetOp):
                span = source_span_of(stmt)
                if span:
                    result.append(SemanticSymbol(stmt.name, uri, "Local", f"function:{fn.name}", {"uri": uri, "range": _word_range(text, span, stmt.name)}))
    return result


def build_index(programs: dict[str, tuple[object, str]]):
    symbols = []
    for uri in sorted(programs):
        program, text = programs[uri]
        symbols.extend(_top_symbols(program, uri, text))
        symbols.extend(_function_symbols(program, uri, text))
    return tuple(symbols)


def symbol_at(program, text, uri, line, character, workspace_programs, visible_imports=None):
    index = build_index(workspace_programs)
    candidates = [s for s in index if s.uri == uri and s.declaration["range"] and _range_contains(s.declaration["range"], line, character)]
    if candidates:
        return _prefer(candidates, line, character)
    # Resolve the AST reference at the cursor, then apply lexical scope rules.
    target_name = None
    for name, span in named_references(program.ast):
        if span is not None and _inside(span, line, character):
            target_name = name
            break
    if target_name is None:
        lines = text.splitlines()
        if 0 <= line < len(lines):
            source = lines[line]
            if 0 <= character <= len(source):
                left = right = character
                while left > 0 and (source[left - 1].isalnum() or source[left - 1] == "_"):
                    left -= 1
                while right < len(source) and (source[right].isalnum() or source[right] == "_"):
                    right += 1
                if left < right:
                    target_name = source[left:right]
    if target_name is None:
        return None
    current_scope = _scope_for_position(program, line, character)
    local = [s for s in index if s.uri == uri and s.name == target_name and (s.scope == current_scope or s.scope == "module")]
    if current_scope != "module":
        fn_local = [s for s in local if s.scope == current_scope]
        if fn_local:
            # Local declarations shadow module symbols.
            return _prefer(fn_local, line, character)
    imported = _imported_symbols(program, text, uri, target_name, index, visible_imports=visible_imports)
    if imported:
        return _prefer(imported, line, character)
    module = [s for s in index if s.uri == uri and s.name == target_name and s.scope == "module"]
    if module:
        return module[0]
    return None


def _prefer(items, line, character):
    return sorted(items, key=lambda s: (0 if _range_contains(s.declaration["range"], line, character) else 1, s.uri, s.scope))[0]


def _range_contains(rng, line, character):
    start, end = rng["start"], rng["end"]
    p = (line, character)
    return (start["line"], start["character"]) <= p <= (end["line"], end["character"])


def _scope_for_position(program, line, character):
    module = getattr(program, "ast", None)
    for fn in getattr(module, "functions", ()) or ():
        if _inside(source_span_of(fn), line, character):
            return f"function:{fn.name}"
    return "module"


def _imported_symbols(program, text, uri, name, index, visible_imports=None):
    import re
    result = []
    imports = list(getattr(getattr(program, "ast", None), "imports", ()) or ())
    # Virtual/open documents may have import lines stripped for tolerant parsing.
    for match in re.finditer(r"(?m)^\s*import\s+(?:[\" ]?)([^\"\s]+)(?:\"?)?(?:\s+as\s+([A-Za-z_]\w*))?(?:\s+\{([^}]+)\})?", text):
        path, alias, names = match.groups()
        allowed = tuple(x.strip() for x in names.split(",")) if names else ()
        imports.append(type("Import", (), {"path": path, "alias": alias, "names": allowed})())
    for imp in imports:
        allowed = set(imp.names or ())
        if allowed and name not in allowed:
            continue
        if visible_imports is not None:
            for symbol in index:
                if symbol.scope == "module" and symbol.name == name and symbol.uri != uri and (symbol.uri, symbol.name) in visible_imports:
                    result.append(symbol)
            continue
        path = str(imp.path).replace("\\", "/")
        base = path.rsplit("/", 1)[-1]
        base_stem = base[:-3] if base.endswith(".sl") else base
        for symbol in index:
            if symbol.scope != "module" or symbol.name != name or symbol.uri == uri:
                continue
            candidate = symbol.uri.rsplit("/", 1)[-1]
            stem = candidate[:-3] if candidate.endswith(".sl") else candidate
            if candidate == base or stem == base_stem:
                result.append(symbol)
    return result


def resolved_references(programs, target: SemanticSymbol, visible_imports=None):
    """Return all references resolved to the exact target symbol."""
    result = []
    index = build_index(programs)
    import re
    pattern = re.compile(r"\b" + re.escape(target.name) + r"\b")
    for uri in sorted(programs):
        program, text = programs[uri]
        allowed = visible_imports.get(uri) if isinstance(visible_imports, dict) else visible_imports
        for line_no, source_line in enumerate(text.splitlines()):
            for match in pattern.finditer(source_line):
                resolved = symbol_at(program, text, uri, line_no, match.start(), programs, visible_imports=allowed)
                if resolved == target:
                    item = {"uri": uri, "range": {"start": {"line": line_no, "character": match.start()}, "end": {"line": line_no, "character": match.end()}}}
                    if item not in result:
                        result.append(item)
    # Declaration itself is not emitted here; caller adds it explicitly.
    return tuple(result)
