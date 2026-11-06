from __future__ import annotations
import json
from typing import Any


def parse(value: str) -> Any:
    return json.loads(value)


def stringify(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def pretty(value: Any) -> str:
    """Serialize a value as human-readable UTF-8 JSON."""
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _path_parts(path: str) -> list[str]:
    if not isinstance(path, str):
        raise TypeError("json path must be Text")
    if path == "":
        return []
    return path.split(".")


def get_path(value: Any, path: str, default: Any = None) -> Any:
    """Safely read a nested JSON value using a dotted path."""
    current = value
    for part in _path_parts(path):
        try:
            if isinstance(current, dict):
                if part not in current:
                    return default
                current = current[part]
            elif isinstance(current, list):
                index = int(part)
                if index < 0 or index >= len(current):
                    return default
                current = current[index]
            else:
                return default
        except (ValueError, TypeError, KeyError, IndexError):
            return default
    return current


def has_path(value: Any, path: str) -> bool:
    marker = object()
    return get_path(value, path, marker) is not marker


def _array_index(part: str, path: str) -> int:
    """Parse an array index and explain path mistakes in user-facing terms."""
    try:
        index = int(part)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"JSON path {path!r} uses {part!r} as an array index; use a whole-number index such as '0' or '1'"
        ) from exc
    if index < 0:
        raise ValueError(f"JSON path {path!r} uses negative array index {index}; indexes start at 0")
    return index


def set_path(value: Any, path: str, replacement: Any) -> Any:
    """Return a copy with a nested JSON value replaced at a dotted path."""
    parts = _path_parts(path)
    if not parts:
        return replacement
    import copy
    result = copy.deepcopy(value)
    current = result
    for position, part in enumerate(parts[:-1]):
        next_part = parts[position + 1]
        if isinstance(current, dict):
            if part not in current or not isinstance(current[part], (dict, list)):
                current[part] = [] if next_part.isdigit() else {}
            current = current[part]
        elif isinstance(current, list):
            index = _array_index(part, path)
            while len(current) <= index:
                current.append({} if not next_part.isdigit() else [])
            current = current[index]
        else:
            raise TypeError(
                f"cannot set JSON path {path!r}: segment {part!r} follows a scalar value; "
                "check that the earlier path segment contains an object or array"
            )
    final = parts[-1]
    if isinstance(current, dict):
        current[final] = replacement
    elif isinstance(current, list):
        index = _array_index(final, path)
        while len(current) <= index:
            current.append(None)
        current[index] = replacement
    else:
        raise TypeError(
            f"cannot set JSON path {path!r}: the target parent is a scalar value; "
            "check the structure before the final path segment"
        )
    return result
