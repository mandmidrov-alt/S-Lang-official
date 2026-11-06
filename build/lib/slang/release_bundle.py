"""Deterministic S-Lang release archive creation and verification helpers."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from .release_manifest import MANIFEST_NAME, build_manifest, write_manifest, verify_manifest

BUNDLE_FORMAT_VERSION = 1
_DEFAULT_DATE_TIME = (1980, 1, 1, 0, 0, 0)


def _included_paths(root: Path) -> list[Path]:
    manifest = build_manifest(root)["files"]
    paths = [root / name for name in manifest]
    manifest_path = root / MANIFEST_NAME
    if manifest_path.exists():
        paths.append(manifest_path)
    return sorted(paths, key=lambda p: p.relative_to(root).as_posix())


def write_bundle(root: str | Path = ".", output: str | Path = "S-Lang-release.zip") -> Path:
    root_path = Path(root).resolve()
    output_path = Path(output).resolve()
    if output_path.parent == root_path:
        raise ValueError("release archive must be outside the release tree")

    write_manifest(root_path)
    verification = verify_manifest(root_path)
    if not verification["valid"]:
        raise ValueError("release manifest is not valid before archiving")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp = output_path.with_suffix(output_path.suffix + ".tmp")
    temp.unlink(missing_ok=True)
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in _included_paths(root_path):
                relative = path.relative_to(root_path).as_posix()
                info = zipfile.ZipInfo(relative, date_time=_DEFAULT_DATE_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes())
        temp.replace(output_path)
    finally:
        temp.unlink(missing_ok=True)
    return output_path


def verify_bundle(path: str | Path) -> dict[str, Any]:
    bundle = Path(path).resolve()
    with zipfile.ZipFile(bundle) as archive:
        bad = archive.testzip()
        if bad is not None:
            return {"valid": False, "error": f"corrupt archive member: {bad}"}
        names = archive.namelist()
        duplicate_names = sorted({n for n in names if names.count(n) > 1})
        if duplicate_names:
            return {"valid": False, "error": "duplicate archive members", "duplicates": duplicate_names}
        if MANIFEST_NAME not in names:
            return {"valid": False, "error": f"missing {MANIFEST_NAME}"}
        manifest = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
        expected = manifest.get("files", {})
        actual: dict[str, str] = {}
        for name in names:
            if name == MANIFEST_NAME:
                continue
            digest = hashlib.sha256(archive.read(name)).hexdigest()
            actual[name] = digest
        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))
        mismatched = sorted(name for name in set(expected) & set(actual) if expected[name] != actual[name])
        valid = not missing and not unexpected and not mismatched and manifest.get("file_count") == len(expected)
        return {
            "valid": valid,
            "file_count": len(actual),
            "expected_file_count": len(expected),
            "missing": missing,
            "unexpected": unexpected,
            "mismatched": mismatched,
        }
