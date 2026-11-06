"""Hover and completion helpers for the S-Lang language server."""
from __future__ import annotations

from dataclasses import is_dataclass, fields as dataclass_fields
from typing import Any

from .ast import BindingDecl, FunctionDecl, PropertyDecl, RecordDecl, EntityDecl, Name, Call, Literal, Binary, Compare, Logical, Conditional, Field, Property, Expr, source_span_of
from .types import NUMBER, BOOLEAN, TEXT, ANY, Type
from .lsp_navigation import _top_level_declarations, _decl_name, _lsp_range, named_references

KEYWORDS = (
    "module", "import", "export", "function", "record", "entity", "let", "state",
    "if", "else", "return", "where", "sort", "map", "aggregate", "reduce", "choose",
    "sequence", "goal", "graph", "path", "satisfy", "simulation", "show", "physics",
)


def _type_ref_text(ref) -> str:
    if ref is None:
        return "Any"
    if not getattr(ref, "args", ()):
        return ref.name
    return f"{ref.name}<" + ", ".join(_type_ref_text(a) for a in ref.args) + ">"


def _signature(decl) -> str:
    if isinstance(decl, FunctionDecl):
        params = ", ".join(f"{name}: {_type_ref_text(ref)}" for name, ref in decl.parameters)
        result = _type_ref_text(decl.return_type) if decl.return_type else "Any"
        return f"function {decl.name}({params}) -> {result}"
    if isinstance(decl, PropertyDecl):
        result = _type_ref_text(decl.return_type) if decl.return_type else "Any"
        return f"property {decl.entity_type}.{decl.name} -> {result}"
    if isinstance(decl, RecordDecl):
        params = f"<{', '.join(decl.type_params)}>" if decl.type_params else ""
        fields = ", ".join(f"{name}: {_type_ref_text(ref)}" for name, ref in decl.fields)
        return f"record {decl.name}{params} {{ {fields} }}"
    if isinstance(decl, EntityDecl):
        fields = ", ".join(f"{name}: {_type_ref_text(ref)}" for name, ref in decl.fields)
        return f"entity {decl.name} {{ {fields} }}"
    if isinstance(decl, BindingDecl):
        return f"let {decl.name}: {_expr_type(decl.expr)}"
    return type(decl).__name__.replace("Decl", "").lower() + f" {getattr(decl, 'name', '')}".rstrip()


def _expr_type(expr, names: dict[str, Type] | None = None) -> Type:
    names = names or {}
    if isinstance(expr, Literal):
        if isinstance(expr.value, bool): return BOOLEAN
        if isinstance(expr.value, (int, float)): return NUMBER
        if isinstance(expr.value, str): return TEXT
        return ANY
    if isinstance(expr, Name):
        return names.get(expr.name, ANY)
    if isinstance(expr, (Compare, Logical)): return BOOLEAN
    if isinstance(expr, Conditional):
        left, right = _expr_type(expr.then_expr, names), _expr_type(expr.else_expr, names)
        return left if left == right else ANY
    if isinstance(expr, Binary):
        if expr.op in {"==", "!=", "<", "<=", ">", ">="}: return BOOLEAN
        left, right = _expr_type(expr.left, names), _expr_type(expr.right, names)
        return left if left == right else ANY
    return ANY


def _binding_types(program, related_programs=()) -> dict[str, Type]:
    names: dict[str, Type] = {}
    declarations = list(_top_level_declarations(program.ast))
    for related in related_programs:
        declarations.extend(_top_level_declarations(related.ast))
    record_names = {decl.name for decl in declarations if isinstance(decl, (RecordDecl, EntityDecl))}
    declarations = list(_top_level_declarations(program.ast))
    for related in related_programs:
        declarations.extend(_top_level_declarations(related.ast))
    for decl in declarations:
        if isinstance(decl, BindingDecl):
            if isinstance(decl.expr, Call) and decl.expr.name in record_names:
                names[decl.name] = Type(decl.expr.name)
            else:
                names[decl.name] = _expr_type(decl.expr, names)
    return names


def _record_fields(program, related_programs=()) -> dict[str, tuple[tuple[str, str], ...]]:
    result: dict[str, tuple[tuple[str, str], ...]] = {}
    declarations = list(_top_level_declarations(program.ast))
    for related in related_programs:
        declarations.extend(_top_level_declarations(related.ast))
    for decl in declarations:
        if isinstance(decl, (RecordDecl, EntityDecl)):
            result[decl.name] = tuple((name, _type_ref_text(ref)) for name, ref in decl.fields)
    return result


def _receiver_at(text: str, line: int, character: int) -> str | None:
    lines = text.splitlines()
    if line < 0 or line >= len(lines):
        return None
    source = lines[line][:max(0, min(character, len(lines[line])))]
    dot = source.rfind(".")
    if dot < 0:
        return None
    left = dot - 1
    while left >= 0 and (source[left].isalnum() or source[left] == "_"):
        left -= 1
    name = source[left + 1:dot]
    return name or None


def _word_at(text: str, line: int, character: int) -> str:
    lines = text.splitlines()
    if line < 0 or line >= len(lines):
        return ""
    source = lines[line]
    character = max(0, min(character, len(source)))
    left = right = character
    while left > 0 and (source[left - 1].isalnum() or source[left - 1] == "_"):
        left -= 1
    while right < len(source) and (source[right].isalnum() or source[right] == "_"):
        right += 1
    return source[left:right]



def _call_context(text: str, line: int, character: int) -> tuple[str, int] | None:
    """Return (function name, active parameter index) for the innermost call."""
    lines = text.splitlines()
    if line < 0 or line >= len(lines):
        return None
    prefix = "\n".join(lines[:line]) + ("\n" if line else "") + lines[line][:character]
    depth = 0
    commas = 0
    open_index = -1
    for i in range(len(prefix) - 1, -1, -1):
        ch = prefix[i]
        if ch == ')':
            depth += 1
        elif ch == '(':
            if depth:
                depth -= 1
            else:
                open_index = i
                break
        elif ch == ',' and depth == 0:
            commas += 1
    if open_index < 0:
        return None
    left = open_index - 1
    while left >= 0 and prefix[left].isspace():
        left -= 1
    end = left + 1
    while left >= 0 and (prefix[left].isalnum() or prefix[left] == '_'):
        left -= 1
    name = prefix[left + 1:end]
    return (name, commas) if name else None




def _type_from_ref(ref) -> Type:
    if ref is None:
        return ANY
    if not getattr(ref, "args", ()):
        return {"Number": NUMBER, "Boolean": BOOLEAN, "Text": TEXT, "Any": ANY}.get(ref.name, Type(ref.name))
    return Type(ref.name, args=tuple(_type_from_ref(arg) for arg in ref.args))


def _function_types(program, related_programs=()) -> dict[str, tuple[tuple[Type, ...], Type]]:
    result = {}
    declarations = list(_top_level_declarations(program.ast))
    for related in related_programs:
        declarations.extend(_top_level_declarations(related.ast))
    for decl in declarations:
        if isinstance(decl, FunctionDecl):
            result[decl.name] = (tuple(_type_from_ref(ref) for _, ref in decl.parameters), _type_from_ref(decl.return_type))
        elif isinstance(decl, (RecordDecl, EntityDecl)):
            result[decl.name] = (tuple(_type_from_ref(ref) for _, ref in decl.fields), Type(decl.name))
    try:
        from .stdlib.registry import signatures as stdlib_signatures
        result.update(stdlib_signatures())
    except Exception:
        pass
    return result


def _expr_type_rich(expr, names: dict[str, Type], functions: dict[str, tuple[tuple[Type, ...], Type]], fields: dict[str, dict[str, Type]]) -> Type:
    if isinstance(expr, Literal):
        if isinstance(expr.value, bool): return BOOLEAN
        if isinstance(expr.value, (int, float)): return NUMBER
        if isinstance(expr.value, str): return TEXT
        return ANY
    if isinstance(expr, Name):
        return names.get(expr.name, functions.get(expr.name, ((), ANY))[1] if expr.name in functions else ANY)
    if isinstance(expr, (Field, Property)):
        base = _expr_type_rich(expr.base, names, functions, fields)
        key = base.name
        return fields.get(key, {}).get(expr.name, ANY)
    if isinstance(expr, Call):
        return functions.get(expr.name, ((), ANY))[1]
    if isinstance(expr, (Compare, Logical)): return BOOLEAN
    if isinstance(expr, Conditional):
        left = _expr_type_rich(expr.then_expr, names, functions, fields)
        right = _expr_type_rich(expr.else_expr, names, functions, fields)
        return left if left == right else ANY
    if isinstance(expr, Binary):
        if expr.op in {"==", "!=", "<", "<=", ">", ">="}: return BOOLEAN
        left = _expr_type_rich(expr.left, names, functions, fields)
        right = _expr_type_rich(expr.right, names, functions, fields)
        return left if left == right else ANY
    return ANY


def _contains_position(span, line: int, character: int) -> bool:
    if span is None or span.start is None:
        return False
    end = span.end or span.start
    pos = (line + 1, character + 1)
    return (span.start.line, span.start.column) <= pos <= (end.line, end.column)


def _iter_exprs(value):
    if isinstance(value, Expr):
        yield value
        for field in dataclass_fields(value):
            yield from _iter_exprs(getattr(value, field.name))
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_exprs(item)
    elif is_dataclass(value) and not isinstance(value, Expr):
        for field in dataclass_fields(value):
            yield from _iter_exprs(getattr(value, field.name))


def _local_context(program, line: int, character: int, related_programs=()) -> dict[str, Type]:
    names = _binding_types(program, related_programs)
    for decl in _top_level_declarations(program.ast):
        if isinstance(decl, FunctionDecl) and _contains_position(source_span_of(decl), line, character):
            for name, ref in decl.parameters:
                names[name] = _type_from_ref(ref)
            for expr in _iter_exprs(decl.body):
                if isinstance(expr, Name):
                    continue
                if isinstance(expr, BindingDecl):
                    names[expr.name] = _expr_type_rich(expr.expr, names, _function_types(program, related_programs), _record_field_types(program, related_programs))
            break
    return names


def _record_field_types(program, related_programs=()) -> dict[str, dict[str, Type]]:
    result = {}
    declarations = list(_top_level_declarations(program.ast))
    for related in related_programs:
        declarations.extend(_top_level_declarations(related.ast))
    for decl in declarations:
        if isinstance(decl, (RecordDecl, EntityDecl)):
            result[decl.name] = {name: _type_from_ref(ref) for name, ref in decl.fields}
    return result


def _expression_at(program, line: int, character: int):
    candidates = []
    for expr in _iter_exprs(program.ast):
        span = source_span_of(expr)
        if _contains_position(span, line, character):
            width = ((span.end or span.start).line - span.start.line) * 100000 + ((span.end or span.start).column - span.start.column)
            candidates.append((width, expr))
    return min(candidates, key=lambda item: item[0])[1] if candidates else None

def signature_help(program, text: str, line: int, character: int, related_programs=()) -> dict | None:
    context = _call_context(text, line, character)
    if context is None:
        return None
    name, active_parameter = context
    declarations = list(_top_level_declarations(program.ast))
    for related in related_programs:
        declarations.extend(_top_level_declarations(related.ast))
    declarations = tuple(declarations)
    for decl in declarations:
        if isinstance(decl, FunctionDecl) and decl.name == name:
            label = _signature(decl)
            return {
                "signatures": [{
                    "label": label,
                    "parameters": [{"label": f"{param}: {_type_ref_text(ref)}"} for param, ref in decl.parameters],
                    "activeParameter": min(active_parameter, max(0, len(decl.parameters) - 1)) if decl.parameters else 0,
                }],
                "activeSignature": 0,
            }
    try:
        from .stdlib.registry import signatures as stdlib_signatures
        builtin = stdlib_signatures().get(name)
    except Exception:
        builtin = None
    if builtin is not None:
        parameters, result_type = builtin
        labels = []
        for index, param in enumerate(parameters):
            labels.append(f"arg{index + 1}: {getattr(param, '__name__', str(param))}")
        result_name = getattr(result_type, "name", str(result_type))
        label = f"function {name}({', '.join(labels)}) -> {result_name}"
        return {
            "signatures": [{
                "label": label,
                "parameters": [{"label": value} for value in labels],
                "activeParameter": min(active_parameter, max(0, len(labels) - 1)) if labels else 0,
            }],
            "activeSignature": 0,
        }
    return None


def hover(program, text: str, line: int, character: int, related_programs=()) -> dict | None:
    word = _word_at(text, line, character)
    if not word:
        return None
    declarations = list(_top_level_declarations(program.ast))
    for related in related_programs:
        declarations.extend(_top_level_declarations(related.ast))
    for decl in declarations:
        if _decl_name(decl) == word:
            signature = _signature(decl)
            return {"contents": {"kind": "markdown", "value": f"```slang\n{signature}\n```"}, "range": _lsp_range(source_span_of(decl))}
    names = _local_context(program, line, character)
    if word in names:
        return {"contents": {"kind": "markdown", "value": f"```slang\n{word}: {names[word]}\n```"}}
    expr = _expression_at(program, line, character)
    if expr is not None:
        typ = _expr_type_rich(expr, names, _function_types(program), _record_field_types(program))
        if typ != ANY:
            return {"contents": {"kind": "markdown", "value": f"```slang\n{typ}\n```"}, "range": _lsp_range(source_span_of(expr))}
    return None


def completion_items(program, text: str, line: int, character: int, related_programs=()) -> tuple[dict, ...]:
    prefix = _word_at(text, line, character)
    candidates: dict[str, dict] = {}
    names = _local_context(program, line, character, related_programs)
    fields = _record_fields(program, related_programs)
    receiver = _receiver_at(text, line, character)
    if receiver is not None:
        receiver_type = names.get(receiver)
        if receiver_type is not None and getattr(receiver_type, "name", None) in fields:
            for name, type_name in fields[receiver_type.name]:
                candidates[name] = {
                    "label": name, "kind": 5, "detail": f"field: {type_name}",
                    "sortText": "0" + name,
                }
            if prefix:
                candidates = {name: item for name, item in candidates.items() if name.lower().startswith(prefix.lower())}
            return tuple(candidates[name] for name in sorted(candidates, key=str.lower))

    declarations = list(_top_level_declarations(program.ast))
    for related in related_programs:
        declarations.extend(_top_level_declarations(related.ast))
    for decl in declarations:
        name = _decl_name(decl)
        if not name: continue
        kind = 3
        if isinstance(decl, (RecordDecl, EntityDecl)): kind = 7
        elif isinstance(decl, PropertyDecl): kind = 10
        detail = _signature(decl)
        item = {"label": name, "kind": kind, "detail": detail}
        if isinstance(decl, FunctionDecl):
            item["sortText"] = "1" + name
        else:
            item["sortText"] = "2" + name
        candidates[name] = item
    for name, typ in names.items():
        candidates.setdefault(name, {"label": name, "kind": 6, "detail": f"local: {typ}", "sortText": "0" + name})
    for keyword in KEYWORDS:
        candidates.setdefault(keyword, {"label": keyword, "kind": 14, "detail": "S-Lang keyword", "sortText": "9" + keyword})
    if prefix:
        candidates = {name: item for name, item in candidates.items() if name.lower().startswith(prefix.lower())}
    return tuple(candidates[name] for name in sorted(candidates, key=lambda value: (candidates[value].get("sortText", ""), value.lower())))



def _edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        current = [i]
        for j, right in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (left != right)))
        previous = current
    return previous[-1]


def code_actions_for_diagnostics(program, text: str, uri: str, diagnostics, *, extra_names=()) -> tuple[dict, ...]:
    """Create safe typo quick-fixes for E2001 unknown-name diagnostics."""
    if program is None:
        return ()
    known = []
    for decl in _top_level_declarations(program.ast):
        name = _decl_name(decl)
        if name:
            known.append(name)
    known = sorted(set(known) | {name for name in extra_names if isinstance(name, str)}, key=str.lower)
    actions = []
    for diagnostic in diagnostics:
        code = getattr(diagnostic, "code", None)
        data = getattr(diagnostic, "data", None) or {}
        if code != "E2001" or not isinstance(data.get("name"), str):
            continue
        name = data["name"]
        candidates = [( _edit_distance(name.lower(), candidate.lower()), candidate) for candidate in known if candidate.lower() != name.lower()]
        candidates = [item for item in candidates if item[0] <= max(1, min(2, len(name) // 2))]
        if not candidates:
            continue
        best_distance = min(item[0] for item in candidates)
        best = [candidate for distance, candidate in candidates if distance == best_distance]
        if len(best) != 1 or diagnostic.span is None:
            continue
        span = diagnostic.span
        end = span.end or span.start
        edit_range = {
            "start": {"line": span.start.line - 1, "character": span.start.column - 1},
            "end": {"line": end.line - 1, "character": end.column - 1},
        }
        replacement = best[0]
        actions.append({
            "title": f"Replace '{name}' with '{replacement}'",
            "kind": "quickfix",
            "diagnostics": [{"code": diagnostic.code, "message": diagnostic.message, "range": edit_range}],
            "edit": {"changes": {uri: [{"range": edit_range, "newText": replacement}]}},
        })
    for diagnostic in diagnostics:
        if getattr(diagnostic, "code", None) != "E2005":
            continue
        data = getattr(diagnostic, "data", {}) or {}
        field_name = data.get("field")
        base_type = str(data.get("base_type", ""))
        if not isinstance(field_name, str):
            continue
        field_table = None
        for type_name, table in _record_field_types(program).items():
            if type_name in base_type:
                field_table = table
                break
        if not field_table:
            continue
        candidates = [( _edit_distance(field_name.lower(), candidate.lower()), candidate) for candidate in field_table if candidate.lower() != field_name.lower()]
        candidates = [item for item in candidates if item[0] <= max(1, min(2, len(field_name) // 2))]
        if not candidates or diagnostic.span is None:
            continue
        distance = min(item[0] for item in candidates)
        best = [candidate for d, candidate in candidates if d == distance]
        if len(best) != 1:
            continue
        span = diagnostic.span
        end = span.end or span.start
        edit_range = {"start": {"line": span.start.line - 1, "character": span.start.column - 1}, "end": {"line": end.line - 1, "character": end.column - 1}}
        replacement = best[0]
        actions.append({
            "title": f"Replace field '{field_name}' with '{replacement}'",
            "kind": "quickfix",
            "diagnostics": [{"code": diagnostic.code, "message": diagnostic.message, "range": edit_range}],
            "edit": {"changes": {uri: [{"range": edit_range, "newText": replacement}]}},
        })
    return tuple(actions)
