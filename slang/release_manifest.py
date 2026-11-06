"""Deterministic release manifest generation and verification for S-Lang."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

MANIFEST_NAME = "release-manifest.json"
MANIFEST_VERSION = 1


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(root: str | Path = ".") -> dict[str, Any]:
    root_path = Path(root).resolve()
    files: dict[str, str] = {}
    for path in sorted(root_path.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root_path).as_posix()
        parts = Path(relative).parts
        if (
            relative == MANIFEST_NAME
            or "__pycache__" in parts
            or ".pytest_cache" in parts
            or ".git" in parts
            or relative.endswith(".pyc")
            or relative.endswith(".tmp")
            or relative.endswith(".bak")
        ):
            continue
        files[relative] = _file_hash(path)
    return {
        "manifest_version": MANIFEST_VERSION,
        "project": "S-Lang",
        "files": files,
        "file_count": len(files),
    }


def write_manifest(root: str | Path = ".", output: str | Path | None = None) -> Path:
    root_path = Path(root).resolve()
    output_path = root_path / (output or MANIFEST_NAME)
    manifest = build_manifest(root_path)
    output_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output_path


def verify_manifest(root: str | Path = ".", manifest_path: str | Path | None = None) -> dict[str, Any]:
    root_path = Path(root).resolve()
    path = root_path / (manifest_path or MANIFEST_NAME)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    expected = manifest.get("files", {})
    actual = build_manifest(root_path)["files"]
    missing = sorted(set(expected) - set(actual))
    unexpected = sorted(set(actual) - set(expected))
    mismatched = sorted(name for name in set(expected) & set(actual) if expected[name] != actual[name])
    ok = not missing and not unexpected and not mismatched and manifest.get("file_count") == len(expected)
    return {
        "valid": ok,
        "file_count": len(actual),
        "expected_file_count": len(expected),
        "missing": missing,
        "unexpected": unexpected,
        "mismatched": mismatched,
    }
