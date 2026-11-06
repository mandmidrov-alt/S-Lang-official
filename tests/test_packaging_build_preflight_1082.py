"""Build dependency preflight tests for the frozen S-Lang runtime."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packaging" / "build-runtime.py"
SPEC = importlib.util.spec_from_file_location("slang_build_runtime", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
BUILD_RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD_RUNTIME)


def _patch_versions(monkeypatch, versions):
    def version(name):
        if name not in versions:
            raise BUILD_RUNTIME.importlib.metadata.PackageNotFoundError(name)
        return versions[name]

    monkeypatch.setattr(BUILD_RUNTIME.importlib.metadata, "version", version)


def test_build_preflight_accepts_pinned_dependencies(monkeypatch):
    _patch_versions(
        monkeypatch,
        {"PyInstaller": "6.16.0", "llvmlite": "0.45.1"},
    )
    monkeypatch.setattr(BUILD_RUNTIME.sys, "version_info", (3, 11, 9))
    BUILD_RUNTIME.check_build_dependencies()


def test_build_preflight_reports_missing_dependency(monkeypatch):
    _patch_versions(monkeypatch, {"llvmlite": "0.45.1"})
    monkeypatch.setattr(BUILD_RUNTIME.sys, "version_info", (3, 11, 9))
    with pytest.raises(SystemExit, match="PyInstaller is not installed") as error:
        BUILD_RUNTIME.check_build_dependencies()
    assert "packaging/requirements-build.txt" in str(error.value)


def test_build_preflight_rejects_mismatched_dependency_versions(monkeypatch):
    _patch_versions(
        monkeypatch,
        {"PyInstaller": "6.16.0", "llvmlite": "0.47.0"},
    )
    monkeypatch.setattr(BUILD_RUNTIME.sys, "version_info", (3, 11, 9))
    with pytest.raises(SystemExit, match=r"llvmlite 0.47.0 is installed"):
        BUILD_RUNTIME.check_build_dependencies()


def test_build_preflight_rejects_unsupported_python(monkeypatch):
    _patch_versions(
        monkeypatch,
        {"PyInstaller": "6.16.0", "llvmlite": "0.45.1"},
    )
    monkeypatch.setattr(BUILD_RUNTIME.sys, "version_info", (3, 14, 0))
    with pytest.raises(SystemExit, match="Unsupported Python version"):
        BUILD_RUNTIME.check_build_dependencies()
