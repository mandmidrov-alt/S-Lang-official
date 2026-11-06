from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_frozen_runtime_uses_release_executable_name():
    builder = (ROOT / "packaging" / "build-runtime.py").read_text(encoding="utf-8")
    assert '("slang1.0" if platform.system() == "Windows" else "slang")' in builder
    assert '("slang1.0.exe" if platform.system() == "Windows" else "slang")' in builder


def test_windows_installers_reference_slang10_executable():
    inno = (ROOT / "packaging" / "windows" / "slang.iss").read_text(encoding="utf-8")
    wix = (ROOT / "packaging" / "windows" / "slang.wxs").read_text(encoding="utf-8")
    install = (ROOT / "packaging" / "windows" / "install.ps1").read_text(encoding="utf-8")
    assert "slang1.0.exe" in inno
    assert "slang1.0.exe" in wix
    assert "slang1.0.exe" in install
    assert "slang.exe" not in inno
    assert "slang.exe" not in wix
    assert "slang.exe" not in install


def test_windows_release_workflows_expect_slang10_executable():
    runtime_workflow = (ROOT / ".github" / "workflows" / "build-runtime.yml").read_text(encoding="utf-8")
    release_workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "dist/windows-x86_64/slang1.0.exe" in runtime_workflow
    assert r"dist\windows-x86_64\slang1.0.exe" in release_workflow
