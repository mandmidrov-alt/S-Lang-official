"""Semantic token generation for the S-Lang Language Server."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

from .lsp_semantic import build_index, symbol_at
from .lsp_navigation import _top_level_declarations
from .ast import EntityDecl, RecordDecl, PropertyDecl, FunctionDecl

TOKEN_TYPES = (
    "namespace", "type", "function", "parameter", "variable", "property",
    "keyword", "number", "string", "operator", "comment",
)
TOKEN_MODIFIERS = ("declaration", "readonly")
TOKEN_TYPE_INDEX = {name: i for i, name in enumerate(TOKEN_TYPES)}

BUILTIN_TYPES = {"Number", "Boolean", "Text", "Any"}

KEYWORDS = {
    "module", "import", "export", "function", "record", "entity", "let", "state",
    "if", "else", "return", "where", "sort", "map", "aggregate", "reduce", "choose",
    "sequence", "goal", "graph", "path", "satisfy", "simulation", "show", "physics",
}

_TOKEN_RE = re.compile(
    r'(?P<comment>//[^\n]*|#[^\n]*)|'
    r'(?P<string>"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')|'
    r'(?P<number>\b(?:0[xX][0-9A-Fa-f]+|(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\b)|'
    r'(?P<identifier>[A-Za-z_][A-Za-z0-9_]*)|'
    r'(?P<operator>==|!=|<=|>=|->|=>|\+|-|\*|/|%|=|<|>|\.|:|,|\(|\)|\[|\]|\{|\})'
)

@dataclass(frozen=True)
class _LexToken:
    text: str
    kind: str
    line: int
    start: int
    end: int


def _lex(text: str) -> tuple[_LexToken, ...]:
    result: list[_LexToken] = []
    for line_no, line in enumerate(text.splitlines()):
        for match in _TOKEN_RE.finditer(line):
            kind = match.lastgroup
            if kind is None:
                continue
            result.append(_LexToken(match.group(0), kind, line_no, match.start(), match.end()))
    return tuple(result)


def _range_contains(rng, line: int, start: int, end: int) -> bool:
    return rng and rng["start"]["line"] == line and rng["start"]["character"] <= start and rng["end"]["character"] >= end


def _declaration_tokens(program, text: str) -> dict[tuple[int, int, int], tuple[str, int]]:
    """Map declaration ranges to (semantic token type, modifier bits)."""
    result = {}
    index = build_index({"file://__current__": (program, text)})
    for symbol in index:
        rng = symbol.declaration.get("range")
        if not rng:
            continue
        kind = symbol.kind
        if kind in {"RecordDecl", "EntityDecl"}:
            token = "type"
        elif kind == "FunctionDecl":
            token = "function"
        elif kind == "PropertyDecl":
            token = "property"
        elif kind == "Parameter":
            token = "parameter"
        else:
            token = "variable"
        result[(rng["start"]["line"], rng["start"]["character"], rng["end"]["character"])] = (token, 1)
    return result


def _type_names(program) -> set[str]:
    return {decl.name for decl in _top_level_declarations(program.ast) if isinstance(decl, (RecordDecl, EntityDecl))}


def _property_names(program) -> set[str]:
    result = set()
    for decl in _top_level_declarations(program.ast):
        if isinstance(decl, (RecordDecl, EntityDecl)):
            result.update(name for name, _ in decl.fields)
        elif isinstance(decl, PropertyDecl):
            result.add(decl.name)
    return result


def semantic_tokens(program, text: str, *, start_line: int | None = None, end_line: int | None = None, visible_names: set[str] | None = None) -> dict:
    """Return LSP SemanticTokens with delta-encoded token data."""
    tokens: list[tuple[int, int, int, int, int]] = []
    declarations = _declaration_tokens(program, text)
    types = _type_names(program)
    properties = _property_names(program)
    lines = text.splitlines()
    for token in _lex(text):
        if token.kind == "comment":
            token_type, modifiers = "comment", 0
        elif token.kind == "string":
            token_type, modifiers = "string", 0
        elif token.kind == "number":
            token_type, modifiers = "number", 0
        elif token.kind == "operator":
            if token.text in {".", ",", ":", "(", ")", "[", "]", "{", "}"}:
                continue
            token_type, modifiers = "operator", 0
        elif token.kind == "identifier":
            if token.text in KEYWORDS:
                token_type, modifiers = "keyword", 0
            else:
                declaration = declarations.get((token.line, token.start, token.end))
                if declaration:
                    token_type, modifiers = declaration
                elif token.text in types or token.text in BUILTIN_TYPES:
                    token_type, modifiers = "type", 0
                elif token.start > 0 and lines[token.line][token.start - 1] == ".":
                    token_type, modifiers = "property", 0
                else:
                    try:
                        resolved = symbol_at(program, text, "file://__current__", token.line, token.start, {"file://__current__": (program, text)})
                    except Exception:
                        resolved = None
                    if resolved is not None:
                        kind = resolved.kind
                        token_type = {
                            "FunctionDecl": "function", "RecordDecl": "type", "EntityDecl": "type",
                            "Parameter": "parameter", "PropertyDecl": "property",
                        }.get(kind, "variable")
                        modifiers = 0
                    elif visible_names is not None and token.text in visible_names:
                        # Imported public symbols are classified semantically, not
                        # merely as generic variables.  The server passes only the
                        # export-aware visible set, so private transitive symbols
                        # cannot leak into semantic highlighting.
                        if token.end < len(lines[token.line]) and lines[token.line][token.end:].lstrip().startswith("("):
                            token_type, modifiers = "function", 0
                        else:
                            token_type, modifiers = "variable", 0
                    elif token.text in properties:
                        token_type, modifiers = "property", 0
                    elif token.end < len(lines[token.line]) and lines[token.line][token.end:].lstrip().startswith("("):
                        token_type, modifiers = "function", 0
                    else:
                        token_type, modifiers = "variable", 0
        else:
            continue
        tokens.append((token.line, token.start, token.end - token.start, TOKEN_TYPE_INDEX[token_type], modifiers))
    if start_line is not None or end_line is not None:
        low = 0 if start_line is None else max(0, start_line)
        high = (10**18 if end_line is None else max(low, end_line))
        tokens = [item for item in tokens if low <= item[0] <= high]
    tokens.sort(key=lambda item: (item[0], item[1], item[3]))
    data: list[int] = []
    previous_line = 0
    previous_start = 0
    for line, start, length, token_type, modifiers in tokens:
        data.extend((line - previous_line, start - previous_start if line == previous_line else start, length, token_type, modifiers))
        previous_line = line
        previous_start = start
    return {"data": data}


__all__ = ["TOKEN_TYPES", "TOKEN_MODIFIERS", "semantic_tokens"]
