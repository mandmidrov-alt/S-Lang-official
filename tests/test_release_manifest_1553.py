from pathlib import Path

from slang.release_manifest import MANIFEST_NAME, build_manifest, verify_manifest, write_manifest


def test_release_manifest_is_deterministic_and_excludes_itself(tmp_path: Path):
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "b.txt").write_text("beta", encoding="utf-8")
    first = write_manifest(tmp_path)
    first_text = first.read_text(encoding="utf-8")
    second = write_manifest(tmp_path)
    assert second.read_text(encoding="utf-8") == first_text
    manifest = build_manifest(tmp_path)
    assert MANIFEST_NAME not in manifest["files"]
    assert manifest["file_count"] == 2


def test_release_manifest_detects_changes(tmp_path: Path):
    (tmp_path / "source.txt").write_text("before", encoding="utf-8")
    write_manifest(tmp_path)
    assert verify_manifest(tmp_path)["valid"]
    (tmp_path / "source.txt").write_text("after", encoding="utf-8")
    result = verify_manifest(tmp_path)
    assert not result["valid"]
    assert result["mismatched"] == ["source.txt"]
