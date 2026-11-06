"""Release self-audit for S-Lang release trees."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .release_bundle import verify_bundle, write_bundle
from .release_manifest import MANIFEST_NAME, verify_manifest

AUDIT_VERSION = 2
_VERSION_RE = re.compile(r"\b(\d+\.\d+(?:\.\d+)?)\b")


def _first_version(text: str) -> str | None:
    match = _VERSION_RE.search(text)
    return match.group(1) if match else None


def _public_line(version: str | None) -> str | None:
    if version is None:
        return None
    parts = version.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else version


def _pyproject_version(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']\s*$', text, re.MULTILINE)
    return match.group(1) if match else None


def _forbidden_files(root: Path) -> list[str]:
    forbidden: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        parts = path.relative_to(root).parts
        if "__pycache__" in parts or ".pytest_cache" in parts or ".git" in parts:
            continue
        if any(part == "build" or part == "dist" or part.endswith(".egg-info") for part in parts):
            forbidden.append(relative)
            continue
        if path.suffix in {".pyc", ".tmp", ".bak"} or path.name in {".coverage"}:
            forbidden.append(relative)
    return sorted(forbidden)


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == MANIFEST_NAME:
            continue
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _reproducibility_check(root: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="slang-release-audit-") as temp:
        base = Path(temp)
        archives: list[Path] = []
        for index in (1, 2):
            copy_root = base / f"tree-{index}"
            shutil.copytree(root, copy_root)
            archive = base / f"release-{index}.zip"
            write_bundle(copy_root, archive)
            archives.append(archive)
        first = archives[0].read_bytes()
        second = archives[1].read_bytes()
        verification = verify_bundle(archives[0])
        return {
            "byte_identical": first == second,
            "sha256": hashlib.sha256(first).hexdigest(),
            "archive_size": len(first),
            "archive_valid": verification["valid"],
            "archive_file_count": verification.get("file_count"),
        }


def audit_release(root: str | Path = ".", archive: str | Path | None = None) -> dict[str, Any]:
    root_path = Path(root).resolve()
    pyproject = root_path / "pyproject.toml"
    readme = root_path / "README.md"
    lsp = root_path / "slang" / "lsp_server.py"

    package_version = _pyproject_version(pyproject) if pyproject.is_file() else None
    readme_version = _first_version(readme.read_text(encoding="utf-8")) if readme.is_file() else None
    lsp_version = None
    if lsp.is_file():
        match = re.search(r'LSP_SERVER_VERSION\s*=\s*["\']([^"\']+)["\']', lsp.read_text(encoding="utf-8"))
        lsp_version = match.group(1) if match else None

    canonical = package_version
    version_values = {
        "pyproject": package_version,
        "readme": readme_version,
        "lsp_server": lsp_version,
    }
    # Package patch versions track compiler builds; README and LSP serverInfo
    # intentionally expose the stable public MAJOR.MINOR language line.
    public_line = _public_line(canonical)
    version_consistent = public_line is not None and all(
        _public_line(value) == public_line for value in (readme_version, lsp_version)
    )
    forbidden = _forbidden_files(root_path)
    manifest = verify_manifest(root_path) if (root_path / MANIFEST_NAME).is_file() else {
        "valid": False, "error": f"missing {MANIFEST_NAME}"
    }

    archive_result = verify_bundle(archive) if archive is not None else None
    reproducibility = _reproducibility_check(root_path)
    checks = {
        "version_consistency": version_consistent,
        "manifest": bool(manifest.get("valid")),
        "forbidden_artifacts": not forbidden,
        "bundle_reproducibility": reproducibility["byte_identical"] and reproducibility["archive_valid"],
        "archive_verification": archive_result is None or bool(archive_result.get("valid")),
    }
    return {
        "audit_version": AUDIT_VERSION,
        "project": "S-Lang",
        "version": canonical,
        "release_ready": all(checks.values()),
        "checks": checks,
        "versions": version_values,
        "forbidden_artifacts": forbidden,
        "manifest": manifest,
        "reproducibility": reproducibility,
        "archive": archive_result,
        "tree_digest": _tree_digest(root_path),
    }
