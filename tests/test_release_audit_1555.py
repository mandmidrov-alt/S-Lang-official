from pathlib import Path

from slang.release_audit import audit_release
from slang.release_manifest import write_manifest
from slang.release_bundle import write_bundle


def _make_tree(root: Path):
    (root / "slang").mkdir(parents=True)
    (root / "slang" / "lsp_server.py").write_text('LSP_SERVER_VERSION = "1.0"\n', encoding="utf-8")
    (root / "pyproject.toml").write_text('[project]\nname = "slang-language"\nversion = "1.0"\n', encoding="utf-8")
    (root / "README.md").write_text('# S-Lang 1.0\n', encoding="utf-8")
    (root / "slang" / "__init__.py").write_text('', encoding="utf-8")
    write_manifest(root)


def test_release_audit_passes_clean_tree(tmp_path: Path):
    _make_tree(tmp_path)
    result = audit_release(tmp_path)
    assert result["release_ready"] is True
    assert all(result["checks"].values())
    assert result["reproducibility"]["byte_identical"] is True


def test_release_audit_detects_stale_version(tmp_path: Path):
    _make_tree(tmp_path)
    (tmp_path / "README.md").write_text('# S-Lang 0.9\n', encoding="utf-8")
    result = audit_release(tmp_path)
    assert result["release_ready"] is False
    assert result["checks"]["version_consistency"] is False


def test_release_audit_detects_forbidden_artifact(tmp_path):
    _make_tree(tmp_path)
    (tmp_path / "bad.tmp").write_bytes(b"bad")
    result = audit_release(tmp_path)
    assert result["release_ready"] is False
    assert result["checks"]["forbidden_artifacts"] is False


def test_release_audit_detects_manifest_drift(tmp_path: Path):
    _make_tree(tmp_path)
    (tmp_path / "README.md").write_text("# S-Lang 1.0\nchanged\n", encoding="utf-8")
    result = audit_release(tmp_path)
    assert result["release_ready"] is False
    assert result["checks"]["manifest"] is False


def test_release_audit_verifies_supplied_archive(tmp_path: Path):
    _make_tree(tmp_path)
    archive = tmp_path.parent / "release.zip"
    write_bundle(tmp_path, archive)
    result = audit_release(tmp_path, archive)
    assert result["release_ready"] is True
    assert result["archive"]["valid"] is True


def test_audit_rejects_generated_build_tree(tmp_path):
    root = tmp_path
    (root / "build" / "lib").mkdir(parents=True)
    (root / "build" / "lib" / "generated.py").write_text("x = 1\n", encoding="utf-8")
    result = audit_release(root)
    assert not result["release_ready"]
    assert result["checks"]["forbidden_artifacts"] is False
    assert "build/lib/generated.py" in result["forbidden_artifacts"]


def test_release_audit_accepts_patch_package_with_stable_public_line(tmp_path: Path):
    _make_tree(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "slang-language"\nversion = "1.0.89"\n',
        encoding="utf-8",
    )
    write_manifest(tmp_path)
    result = audit_release(tmp_path)
    assert result["release_ready"] is True
    assert result["versions"] == {"pyproject": "1.0.89", "readme": "1.0", "lsp_server": "1.0"}
