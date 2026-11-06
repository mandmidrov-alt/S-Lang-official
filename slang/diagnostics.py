"""Deterministic diagnostics and source-location primitives for S-Lang 1.15.

The diagnostic model is intentionally independent of the parser and semantic
compiler. Front-end stages can attach a source span when they have one, while
later stages may emit a diagnostic without a span until AST source locations
are available.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
import json
from typing import Iterable, Mapping


class DiagnosticSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class DiagnosticFieldSchema:
    name: str
    value_type: str
    required: bool = False
    description: str | None = None
    enum: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiagnosticPayloadSchema:
    fields: tuple[DiagnosticFieldSchema, ...] = ()

    @property
    def required_fields(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.fields if field.required)

    def field(self, name: str) -> DiagnosticFieldSchema | None:
        return next((field for field in self.fields if field.name == name), None)


@dataclass(frozen=True)
class DiagnosticDefinition:
    code: str
    phase: str
    message: str
    severity: DiagnosticSeverity = DiagnosticSeverity.ERROR
    hint: str | None = None
    category: str = "compiler"
    tags: tuple[str, ...] = ()
    schema: DiagnosticPayloadSchema = DiagnosticPayloadSchema()


_SCHEMA = DiagnosticPayloadSchema
_F = DiagnosticFieldSchema


_DIAGNOSTIC_DEFINITIONS = {
    "E0001": DiagnosticDefinition("E0001", "compiler", "internal compiler error", category="internal", tags=("internal",)),
    "E1000": DiagnosticDefinition("E1000", "parse", "syntax error", hint="check the syntax near the highlighted range", category="syntax", tags=("syntax", "parse")),
    "E2000": DiagnosticDefinition("E2000", "semantic", "type or semantic error", hint="check the types and declarations involved", category="type", tags=("semantic", "type"), schema=_SCHEMA((_F("operator", "string"), _F("left_type", "type"), _F("right_type", "type"), _F("expected_type", "type"), _F("actual_type", "type"), _F("construct", "string"), _F("name", "string")))),
    "E2001": DiagnosticDefinition("E2001", "semantic", "unknown name", hint="declare the name before using it", category="name", tags=("semantic", "name", "resolution"), schema=_SCHEMA((_F("name", "string", True),))),
    "E2002": DiagnosticDefinition("E2002", "semantic", "unknown function", hint="check the function name and available imports", category="name", tags=("semantic", "name", "function", "resolution"), schema=_SCHEMA((_F("function", "string", True),))),
    "E2003": DiagnosticDefinition("E2003", "semantic", "wrong argument count", hint="pass the number of arguments required by the function", category="arity", tags=("semantic", "call", "arity"), schema=_SCHEMA((_F("function", "string", True), _F("expected_arity", "integer", True), _F("actual_arity", "integer", True)))),
    "E2004": DiagnosticDefinition("E2004", "semantic", "argument type mismatch", hint="pass an argument compatible with the expected type", category="type", tags=("semantic", "call", "type"), schema=_SCHEMA((_F("function", "string"), _F("argument", "integer"), _F("expected_type", "type", True), _F("actual_type", "type", True), _F("operator", "string")))),
    "E2005": DiagnosticDefinition("E2005", "semantic", "invalid field or property", hint="check the available fields or properties", category="field", tags=("semantic", "field", "property"), schema=_SCHEMA((_F("field", "string", True), _F("base_type", "type", True)))),
    "E2006": DiagnosticDefinition("E2006", "semantic", "invalid condition type", hint="use a Boolean expression as the condition", category="condition", tags=("semantic", "condition", "boolean"), schema=_SCHEMA((_F("expected_type", "type", True), _F("actual_type", "type", True), _F("operator", "string"), _F("operand", "string", enum=("left", "right")), _F("construct", "string")))),
    "E3000": DiagnosticDefinition("E3000", "compiler", "invalid compiler value", hint="check the declaration or compiler option", category="compiler", tags=("compiler", "value")),
}


def diagnostic_definition(code: str) -> DiagnosticDefinition | None:
    return _DIAGNOSTIC_DEFINITIONS.get(code)


def diagnostic_definitions() -> tuple[DiagnosticDefinition, ...]:
    return tuple(_DIAGNOSTIC_DEFINITIONS.values())


def diagnostic_schema(code: str) -> DiagnosticPayloadSchema | None:
    definition = diagnostic_definition(code)
    return definition.schema if definition is not None else None


def diagnostic_schemas() -> dict[str, DiagnosticPayloadSchema]:
    return {code: definition.schema for code, definition in _DIAGNOSTIC_DEFINITIONS.items()}


def _value_matches_schema(value, field: DiagnosticFieldSchema) -> bool:
    if field.value_type in ("string", "type"):
        return isinstance(value, str)
    if field.value_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if field.value_type == "boolean":
        return isinstance(value, bool)
    if field.value_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return True


def validate_diagnostic_data(code: str, data: Mapping | None) -> tuple[str, ...]:
    schema = diagnostic_schema(code)
    if schema is None or data is None:
        return ()
    errors = []
    for field in schema.fields:
        if field.required and field.name not in data:
            errors.append(f"missing required diagnostic field '{field.name}'")
    for name, value in data.items():
        field = schema.field(name)
        if field is None:
            errors.append(f"unknown diagnostic field '{name}' for {code}")
            continue
        if not _value_matches_schema(value, field):
            errors.append(f"diagnostic field '{name}' must be {field.value_type}")
            continue
        if field.enum and value not in field.enum:
            errors.append(f"diagnostic field '{name}' must be one of {field.enum}")
    return tuple(errors)


@dataclass(frozen=True)
class SourcePosition:
    line: int
    column: int


@dataclass(frozen=True)
class SourceSpan:
    start: SourcePosition
    end: SourcePosition | None = None

    @classmethod
    def line(cls, line: int, column: int = 1, end_column: int | None = None):
        end = SourcePosition(line, end_column) if end_column is not None else None
        return cls(SourcePosition(line, column), end)

    @classmethod
    def range(cls, start_line: int, start_column: int, end_line: int, end_column: int):
        return cls(
            SourcePosition(start_line, start_column),
            SourcePosition(end_line, end_column),
        )


@dataclass(frozen=True)
class DiagnosticRelatedSpan:
    span: SourceSpan
    label: str | None = None

    def to_dict(self) -> dict:
        data = {
            "location": {
                "line": self.span.start.line,
                "column": self.span.start.column,
            }
        }
        if self.span.end is not None:
            data["location"]["end_line"] = self.span.end.line
            data["location"]["end_column"] = self.span.end.column
        if self.label is not None:
            data["label"] = self.label
        return data


@dataclass(frozen=True)
class Diagnostic:
    severity: DiagnosticSeverity
    message: str
    code: str = "E0000"
    phase: str = "compiler"
    span: SourceSpan | None = None
    path: str | None = None
    related: tuple[DiagnosticRelatedSpan, ...] = ()
    notes: tuple[str, ...] = ()
    hint: str | None = None
    category: str | None = None
    tags: tuple[str, ...] = ()
    data: dict | None = None

    def validate_data(self) -> tuple[str, ...]:
        return validate_diagnostic_data(self.code, self.data)

    def to_dict(self) -> dict:
        data = {
            "severity": self.severity.value,
            "code": self.code,
            "phase": self.phase,
            "message": self.message,
        }
        definition = diagnostic_definition(self.code)
        category = self.category or (definition.category if definition is not None else None)
        tags = self.tags or (definition.tags if definition is not None else ())
        if category is not None:
            data["category"] = category
        if tags:
            data["tags"] = list(tags)
        schema = diagnostic_schema(self.code)
        if schema is not None and schema.fields:
            data["schema"] = {
                "fields": [
                    {
                        "name": field.name,
                        "type": field.value_type,
                        "required": field.required,
                        **({"description": field.description} if field.description else {}),
                        **({"enum": list(field.enum)} if field.enum else {}),
                    }
                    for field in schema.fields
                ]
            }
        if self.data:
            data["data"] = dict(self.data)
        if self.path is not None:
            data["path"] = self.path
        if self.span is not None:
            data["location"] = {
                "line": self.span.start.line,
                "column": self.span.start.column,
            }
            if self.span.end is not None:
                data["location"]["end_line"] = self.span.end.line
                data["location"]["end_column"] = self.span.end.column
        if self.related:
            data["related"] = [item.to_dict() for item in self.related]
        if self.notes:
            data["notes"] = list(self.notes)
        if self.hint is not None:
            data["hint"] = self.hint
        return data


DIAGNOSTIC_PROTOCOL_NAME = "slang-diagnostics"
DIAGNOSTIC_PROTOCOL_VERSION = 1


def _position_from_dict(value: Mapping, *, field: str) -> SourcePosition:
    if not isinstance(value, Mapping):
        raise ValueError(f"diagnostic {field} must be an object")
    try:
        line = value["line"]
        column = value["column"]
    except KeyError as exc:
        raise ValueError(f"diagnostic {field} is missing {exc.args[0]!r}") from None
    if not isinstance(line, int) or isinstance(line, bool) or line < 1:
        raise ValueError(f"diagnostic {field}.line must be a positive integer")
    if not isinstance(column, int) or isinstance(column, bool) or column < 1:
        raise ValueError(f"diagnostic {field}.column must be a positive integer")
    return SourcePosition(line, column)


def _span_from_dict(value: Mapping, *, field: str = "location") -> SourceSpan:
    if not isinstance(value, Mapping):
        raise ValueError(f"diagnostic {field} must be an object")
    start = _position_from_dict(value, field=field)
    if "end_line" not in value and "end_column" not in value:
        return SourceSpan(start)
    if "end_line" not in value or "end_column" not in value:
        raise ValueError(f"diagnostic {field} must contain both end_line and end_column")
    end = _position_from_dict(
        {"line": value["end_line"], "column": value["end_column"]},
        field=f"{field}.end",
    )
    return SourceSpan(start, end)


def _diagnostic_from_payload(payload: Mapping) -> Diagnostic:
    if not isinstance(payload, Mapping):
        raise ValueError("diagnostic payload must be an object")
    required = ("severity", "code", "phase", "message")
    for key in required:
        if key not in payload:
            raise ValueError(f"diagnostic payload is missing {key!r}")
    try:
        severity = DiagnosticSeverity(payload["severity"])
    except ValueError as exc:
        raise ValueError(f"unknown diagnostic severity {payload['severity']!r}") from exc
    code = payload["code"]
    phase = payload["phase"]
    message = payload["message"]
    if not all(isinstance(value, str) for value in (code, phase, message)):
        raise ValueError("diagnostic code, phase and message must be strings")

    location = payload.get("location")
    span = _span_from_dict(location) if location is not None else None
    related_items = []
    for index, item in enumerate(payload.get("related", ())):
        if not isinstance(item, Mapping) or "location" not in item:
            raise ValueError(f"diagnostic related[{index}] must contain location")
        related_items.append(DiagnosticRelatedSpan(_span_from_dict(item["location"], field=f"related[{index}].location"), item.get("label")))

    data = payload.get("data")
    if data is not None and not isinstance(data, Mapping):
        raise ValueError("diagnostic data must be an object")
    if data is not None:
        errors = validate_diagnostic_data(code, data)
        if errors:
            raise ValueError("invalid diagnostic data: " + "; ".join(errors))

    category = payload.get("category")
    tags = payload.get("tags", [])
    notes = payload.get("notes", [])
    hint = payload.get("hint")
    if category is not None and not isinstance(category, str):
        raise ValueError("diagnostic category must be a string")
    if not isinstance(tags, list) or not all(isinstance(item, str) for item in tags):
        raise ValueError("diagnostic tags must be an array of strings")
    if not isinstance(notes, list) or not all(isinstance(item, str) for item in notes):
        raise ValueError("diagnostic notes must be an array of strings")
    if hint is not None and not isinstance(hint, str):
        raise ValueError("diagnostic hint must be a string")
    path = payload.get("path")
    if path is not None and not isinstance(path, str):
        raise ValueError("diagnostic path must be a string")
    return Diagnostic(
        severity,
        message,
        code=code,
        phase=phase,
        span=span,
        path=path,
        related=tuple(related_items),
        notes=tuple(notes),
        hint=hint,
        category=category,
        tags=tuple(tags),
        data=dict(data) if data is not None else None,
    )


def diagnostic_to_protocol_dict(diagnostic: Diagnostic) -> dict:
    """Return the versioned, machine-readable diagnostic protocol envelope."""
    return {
        "protocol": {
            "name": DIAGNOSTIC_PROTOCOL_NAME,
            "version": DIAGNOSTIC_PROTOCOL_VERSION,
        },
        "diagnostic": diagnostic.to_dict(),
    }


def diagnostics_to_protocol_dict(diagnostics: Iterable[Diagnostic]) -> dict:
    """Return a versioned protocol envelope containing an ordered diagnostic list."""
    return {
        "protocol": {
            "name": DIAGNOSTIC_PROTOCOL_NAME,
            "version": DIAGNOSTIC_PROTOCOL_VERSION,
        },
        "diagnostics": [diagnostic.to_dict() for diagnostic in diagnostics],
    }


def _canonical_json(value: Mapping) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def serialize_diagnostic(diagnostic: Diagnostic) -> str:
    """Serialize one diagnostic using the canonical S-Lang diagnostic protocol."""
    return _canonical_json(diagnostic_to_protocol_dict(diagnostic))


def serialize_diagnostics(diagnostics: Iterable[Diagnostic]) -> str:
    """Serialize an ordered diagnostic sequence using canonical JSON."""
    return _canonical_json(diagnostics_to_protocol_dict(diagnostics))


def _protocol_payload(payload: Mapping, *, plural: bool) -> Mapping:
    if not isinstance(payload, Mapping):
        raise ValueError("diagnostic protocol payload must be an object")
    protocol = payload.get("protocol")
    if not isinstance(protocol, Mapping):
        raise ValueError("diagnostic protocol payload is missing 'protocol'")
    if protocol.get("name") != DIAGNOSTIC_PROTOCOL_NAME:
        raise ValueError(f"unsupported diagnostic protocol {protocol.get('name')!r}")
    if protocol.get("version") != DIAGNOSTIC_PROTOCOL_VERSION:
        raise ValueError(f"unsupported diagnostic protocol version {protocol.get('version')!r}")
    key = "diagnostics" if plural else "diagnostic"
    if key not in payload:
        raise ValueError(f"diagnostic protocol payload is missing {key!r}")
    return payload[key]


def deserialize_diagnostic(serialized: str | bytes | Mapping) -> Diagnostic:
    """Deserialize one canonical diagnostic protocol payload."""
    payload = json.loads(serialized) if isinstance(serialized, (str, bytes)) else serialized
    diagnostic = _protocol_payload(payload, plural=False)
    return _diagnostic_from_payload(diagnostic)


def deserialize_diagnostics(serialized: str | bytes | Mapping) -> tuple[Diagnostic, ...]:
    """Deserialize an ordered diagnostic protocol payload."""
    payload = json.loads(serialized) if isinstance(serialized, (str, bytes)) else serialized
    diagnostics = _protocol_payload(payload, plural=True)
    if not isinstance(diagnostics, list):
        raise ValueError("diagnostic protocol 'diagnostics' must be an array")
    return tuple(_diagnostic_from_payload(item) for item in diagnostics)


# LSP diagnostic adapter. The compiler remains independent of the LSP protocol;
# these helpers only translate the stable S-Lang diagnostic model at the boundary.
LSP_DIAGNOSTIC_SOURCE = "slang"


def _lsp_severity(severity: DiagnosticSeverity) -> int:
    return {
        DiagnosticSeverity.ERROR: 1,
        DiagnosticSeverity.WARNING: 2,
        DiagnosticSeverity.INFO: 3,
    }[severity]


def _lsp_position(position: SourcePosition) -> dict:
    # S-Lang source positions are 1-based; LSP positions are 0-based.
    return {"line": max(position.line - 1, 0), "character": max(position.column - 1, 0)}


def _lsp_range(span: SourceSpan | None) -> dict:
    if span is None:
        point = {"line": 0, "character": 0}
        return {"start": point, "end": dict(point)}
    end = span.end or span.start
    return {"start": _lsp_position(span.start), "end": _lsp_position(end)}


def _path_to_uri(path: str | None) -> str | None:
    if path is None:
        return None
    if path.startswith("file://"):
        return path
    from pathlib import Path
    return Path(path).absolute().as_uri()


def diagnostic_to_lsp(diagnostic: Diagnostic, *, source: str = LSP_DIAGNOSTIC_SOURCE) -> dict:
    """Convert one S-Lang diagnostic to an LSP Diagnostic object."""
    result = {
        "range": _lsp_range(diagnostic.span),
        "severity": _lsp_severity(diagnostic.severity),
        "code": diagnostic.code,
        "source": source,
        "message": diagnostic.message,
    }
    if diagnostic.tags:
        # Keep S-Lang tags in data rather than pretending they are LSP DiagnosticTag values.
        result.setdefault("data", {})["slang_tags"] = list(diagnostic.tags)
    if diagnostic.category is not None:
        result.setdefault("data", {})["slang_category"] = diagnostic.category
    if diagnostic.phase:
        result.setdefault("data", {})["slang_phase"] = diagnostic.phase
    if diagnostic.hint is not None:
        result.setdefault("data", {})["hint"] = diagnostic.hint
    if diagnostic.data:
        result.setdefault("data", {})["diagnostic_data"] = dict(diagnostic.data)
    if diagnostic.notes:
        result.setdefault("data", {})["notes"] = list(diagnostic.notes)
    if diagnostic.related:
        uri = _path_to_uri(diagnostic.path)
        if uri is not None:
            result["relatedInformation"] = [
                {
                    "location": {"uri": uri, "range": _lsp_range(item.span)},
                    "message": item.label or diagnostic.message,
                }
                for item in diagnostic.related
            ]
    return result


def diagnostics_to_lsp(diagnostics: Iterable[Diagnostic], *, source: str = LSP_DIAGNOSTIC_SOURCE) -> list[dict]:
    """Convert an ordered diagnostic sequence to LSP Diagnostic objects."""
    return [diagnostic_to_lsp(item, source=source) for item in diagnostics]


def diagnostics_to_lsp_publish(
    diagnostics: Iterable[Diagnostic], *, uri: str | None = None, version: int | None = None,
    source: str = LSP_DIAGNOSTIC_SOURCE
) -> dict:
    """Build the LSP PublishDiagnosticsParams payload for one source document."""
    items = tuple(diagnostics)
    if uri is None:
        uri = _path_to_uri(items[0].path) if items else None
    if uri is None:
        raise ValueError("an LSP publishDiagnostics payload requires a URI or a diagnostic path")
    result = {"uri": uri, "diagnostics": diagnostics_to_lsp(items, source=source)}
    if version is not None:
        result["version"] = version
    return result


def diagnostics_to_lsp_publish_documents(
    diagnostics: Iterable[Diagnostic], *, uris: Iterable[str] = (),
    versions: Mapping[str, int] | None = None, source: str = LSP_DIAGNOSTIC_SOURCE
) -> list[dict]:
    """Group diagnostics by URI and build stable PublishDiagnosticsParams payloads.

    ``uris`` may include clean documents so they receive an empty diagnostic list,
    which is how an LSP client clears stale diagnostics after successful compilation.
    """
    groups: dict[str, list[Diagnostic]] = {}
    for item in diagnostics:
        uri = _path_to_uri(item.path)
        if uri is None:
            raise ValueError("document diagnostics require a diagnostic path or explicit URI")
        groups.setdefault(uri, []).append(item)
    for uri in uris:
        groups.setdefault(uri, [])
    versions = versions or {}
    return [
        diagnostics_to_lsp_publish(
            groups[uri], uri=uri, version=versions.get(uri), source=source
        )
        for uri in sorted(groups)
    ]


class DiagnosticBag:
    """Stable ordered collection of diagnostics."""

    def __init__(self, diagnostics: Iterable[Diagnostic] = ()):
        self._items = list(diagnostics)

    def add(self, diagnostic: Diagnostic) -> None:
        self._items.append(diagnostic)

    def extend(self, diagnostics: Iterable[Diagnostic]) -> None:
        self._items.extend(diagnostics)

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        return tuple(self._items)

    @property
    def has_errors(self) -> bool:
        return any(d.severity == DiagnosticSeverity.ERROR for d in self._items)

    def to_dict(self) -> list[dict]:
        return [d.to_dict() for d in self._items]

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


_CURRENT_SOURCE_LOCATION: ContextVar[SourceSpan | None] = ContextVar(
    "slang_current_source_location", default=None
)
_CURRENT_SOURCE_TEXT: ContextVar[str | None] = ContextVar(
    "slang_current_source_text", default=None
)


def current_source_location() -> SourceSpan | None:
    return _CURRENT_SOURCE_LOCATION.get()


def current_source_text() -> str | None:
    return _CURRENT_SOURCE_TEXT.get()


@contextmanager
def source_location(
    line: int,
    column: int = 1,
    end_column: int | None = None,
    source_text: str | None = None,
):
    token = _CURRENT_SOURCE_LOCATION.set(SourceSpan.line(line, column, end_column))
    text_token = _CURRENT_SOURCE_TEXT.set(source_text)
    try:
        yield
    finally:
        _CURRENT_SOURCE_LOCATION.reset(token)
        _CURRENT_SOURCE_TEXT.reset(text_token)


def set_source_location(
    line: int,
    column: int = 1,
    end_column: int | None = None,
    source_text: str | None = None,
):
    """Set the parser's current best-effort source location.

    This is used by the legacy line-oriented parser until source spans are
    attached directly to AST nodes. The value is context-local and therefore
    safe for concurrent compiler invocations.
    """
    _CURRENT_SOURCE_LOCATION.set(SourceSpan.line(line, column, end_column))
    _CURRENT_SOURCE_TEXT.set(source_text)


def diagnostic_from_exception(exc: Exception, *, path: str | None = None) -> Diagnostic:
    if isinstance(exc, SyntaxError):
        phase = "parse"
        severity = DiagnosticSeverity.ERROR
        code = "E1000"
    elif exc.__class__.__name__ == "ParseError":
        phase = "parse"
        severity = DiagnosticSeverity.ERROR
        code = getattr(exc, "code", "E1000")
    elif isinstance(exc, TypeError):
        phase = "semantic"
        severity = DiagnosticSeverity.ERROR
        code = "E2000"
    elif isinstance(exc, ValueError):
        phase = "compiler"
        severity = DiagnosticSeverity.ERROR
        code = "E3000"
    else:
        phase = "compiler"
        severity = DiagnosticSeverity.ERROR
        code = "E0001"

    explicit_code = getattr(exc, "diagnostic_code", None)
    if explicit_code:
        code = explicit_code
        definition = diagnostic_definition(code)
        if definition is not None:
            phase = definition.phase
            severity = definition.severity
    span = getattr(exc, "span", None) or current_source_location()
    related = tuple(getattr(exc, "related_spans", ()))
    notes = tuple(getattr(exc, "notes", ()))
    diagnostic_data = getattr(exc, "diagnostic_data", None)
    hint = _beginner_friendly_hint(code, diagnostic_data)
    if hint is None and phase == "parse":
        hint = _import_resolution_hint(str(exc))
    if hint is None:
        hint = getattr(exc, "hint", None)
    if hint is None:
        definition = diagnostic_definition(code)
        if definition is not None:
            hint = definition.hint
    definition = diagnostic_definition(code)
    category = getattr(exc, "diagnostic_category", None)
    tags = tuple(getattr(exc, "diagnostic_tags", ()))
    return Diagnostic(
        severity, str(exc), code=code, phase=phase, span=span, path=path,
        related=related, notes=notes, hint=hint, category=category, tags=tags,
        data=diagnostic_data,
    )



def _beginner_friendly_hint(code: str, data: Mapping | None) -> str | None:
    """Build a concise actionable hint from stable structured diagnostic data.

    Keep the primary diagnostic message and code unchanged; these hints are
    supplementary and are also exposed to editor integrations.
    """
    if not isinstance(data, Mapping):
        return None
    if code == "E2004":
        expected = data.get("expected_type")
        actual = data.get("actual_type")
        function = data.get("function")
        argument = data.get("argument")
        if isinstance(expected, str) and isinstance(actual, str):
            if isinstance(function, str) and isinstance(argument, int) and not isinstance(argument, bool):
                return (
                    f"Argument {argument} of '{function}' expects {expected}, but received {actual}. "
                    "Pass a value of the expected type or convert it before this call."
                )
            return f"Expected {expected}, but received {actual}. Check the value's type or convert it before use."
    if code == "E2006":
        expected = data.get("expected_type")
        actual = data.get("actual_type")
        construct = data.get("construct")
        if expected == "Boolean" and isinstance(actual, str):
            where = {
                "if_statement": "the if condition",
                "conditional": "the conditional expression",
                "while_statement": "the while condition",
            }.get(construct, "this condition")
            return f"{where.capitalize()} must be Boolean, but the expression has type {actual}. Compare values or use a Boolean expression."
    if code == "E2000":
        operator = data.get("operator")
        left = data.get("left_type")
        right = data.get("right_type")
        if isinstance(operator, str) and isinstance(left, str) and isinstance(right, str):
            return f"Operator '{operator}' cannot combine {left} and {right}. Use compatible values or convert one operand."
        expected = data.get("expected_type")
        actual = data.get("actual_type")
        if isinstance(expected, str) and isinstance(actual, str):
            return f"This construct expects {expected}, but received {actual}. Check the value or convert it to a compatible type."
    if code == "E2003":
        function = data.get("function")
        expected = data.get("expected_arity")
        actual = data.get("actual_arity")
        if isinstance(function, str) and isinstance(expected, int) and isinstance(actual, int):
            return f"'{function}' expects {expected} argument(s), but {actual} were provided. Add or remove arguments to match the function call."
    return None


def _import_resolution_hint(message: str) -> str | None:
    """Explain common module-resolution failures without changing their codes."""
    text = message.lower()
    if "import not found:" in text:
        return (
            "Check the path in the import statement, including its spelling and .sl extension. "
            "Relative imports are resolved from the importing file's directory and project source roots."
        )
    if "re-export source not found:" in text:
        return (
            "Check the path after the export declaration and make sure the source module exists. "
            "Re-export paths use the same resolution rules as imports."
        )
    if "does not publicly export:" in text or "does not export:" in text:
        return (
            "The requested name is not available through this module's public interface. "
            "Check its spelling and the module's export declaration, or import a name that is public."
        )
    if "exports unknown declaration" in text or "exports unknown declaration(s)" in text:
        return (
            "The export list names a declaration that the module does not define. "
            "Check the spelling and make sure the function, record, or entity is declared in that module."
        )
    if "cyclic import:" in text:
        return (
            "These modules import one another in a cycle. Move shared declarations into a separate module "
            "that both modules can import."
        )
    if "unknown standard-library module:" in text:
        return (
            "Check the standard-library module name against the S-Lang documentation; "
            "standard-library imports use the form import std.module_name."
        )
    if "module imports itself:" in text:
        return "Remove the import that points back to the same module."
    if "duplicate imported namespace" in text:
        return "Give each imported module a distinct alias, or remove the duplicate import."
    return None


def diagnostics_for_source(source: str, *, path: str | None = None, base_dir=None) -> DiagnosticBag:
    """Parse and validate source, returning stable diagnostics instead of raising.

    ``base_dir`` is the directory used to resolve relative imports. ``path`` is
    retained as the diagnostic display path and does not affect import lookup.
    """
    from .core import parse, validate

    try:
        program = parse(source, base_dir)
        validate(program)
    except Exception as exc:
        return DiagnosticBag((diagnostic_from_exception(exc, path=path),))
    return DiagnosticBag()


def format_diagnostic(diagnostic: Diagnostic, source: str | None = None) -> str:
    location = ""
    if diagnostic.path:
        location += diagnostic.path
    if diagnostic.span:
        prefix = ":" if location else ""
        start = diagnostic.span.start
        end = diagnostic.span.end
        location += f"{prefix}{start.line}:{start.column}"
        if end is not None and (end.line != start.line or end.column != start.column):
            location += f"-{end.line}:{end.column}"
    if not location:
        location = "<source>"
    head = f"{location}: {diagnostic.severity.value}[{diagnostic.code}]: {diagnostic.message}"
    if source is None or diagnostic.span is None:
        return head
    lines = source.splitlines()
    line_index = diagnostic.span.start.line - 1
    if not 0 <= line_index < len(lines):
        return head
    text = lines[line_index]
    column = max(1, diagnostic.span.start.column)
    end = diagnostic.span.end
    if end is not None and end.line == diagnostic.span.start.line:
        end_column = max(column + 1, end.column)
        width = max(1, end_column - column)
        marker = "^" * width
    else:
        marker = "^"
    rendered = f"{head}\n  {text}\n  {' ' * (column - 1)}{marker}"
    if end is not None and end.line != diagnostic.span.start.line:
        rendered += f"\n  ... through line {end.line}:{end.column}"
    for item in diagnostic.related:
        start = item.span.start
        label = f" ({item.label})" if item.label else ""
        rendered += f"\n  note: {start.line}:{start.column}"
        if item.span.end is not None and (item.span.end.line != start.line or item.span.end.column != start.column):
            rendered += f"-{item.span.end.line}:{item.span.end.column}"
        rendered += label
    for note in diagnostic.notes:
        rendered += f"\n  note: {note}"
    if diagnostic.hint is not None:
        rendered += f"\n  help: {diagnostic.hint}"
    return rendered


def format_diagnostics(diagnostics: Iterable[Diagnostic], source: str | None = None) -> str:
    return "\n".join(format_diagnostic(d, source) for d in diagnostics)
