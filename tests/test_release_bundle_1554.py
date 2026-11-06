from pathlib import Path
from zipfile import ZipFile

from slang.release_bundle import verify_bundle, write_bundle


def test_release_bundle_is_deterministic_and_self_verified(tmp_path: Path):
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "b.txt").write_text("beta", encoding="utf-8")
    first = tmp_path.parent / "first.zip"
    second = tmp_path.parent / "second.zip"
    write_bundle(tmp_path, first)
    write_bundle(tmp_path, second)
    assert first.read_bytes() == second.read_bytes()
    result = verify_bundle(first)
    assert result["valid"] is True
    with ZipFile(first) as archive:
        assert "release-manifest.json" in archive.namelist()


def test_release_bundle_detects_tampering(tmp_path: Path):
    (tmp_path / "source.txt").write_text("before", encoding="utf-8")
    archive_path = tmp_path.parent / "release.zip"
    write_bundle(tmp_path, archive_path)
    with ZipFile(archive_path, "a") as archive:
        archive.writestr("source.txt", b"after")
    result = verify_bundle(archive_path)
    assert result["valid"] is False
