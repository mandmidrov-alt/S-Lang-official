import zipfile

from slang.project import (
    install_package,
    package_archive,
    publish_package,
    registry_list,
    resolve_dependencies,
    write_lock,
)


def manifest(path, name, version, deps=""):
    path.write_text(
        f'[package]\nname = "{name}"\nversion = "{version}"\nsource_roots = ["."]\n\n[dependencies]\n{deps}',
        encoding="utf-8",
    )


def test_package_archive_is_deterministic(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    manifest(pkg / "slang.toml", "demo", "1.2.0")
    (pkg / "main.sl").write_text("module demo\nlet x = 1\n", encoding="utf-8")
    a = package_archive(pkg, tmp_path / "a.slpkg")
    b = package_archive(pkg, tmp_path / "b.slpkg")
    assert a.read_bytes() == b.read_bytes()
    with zipfile.ZipFile(a) as zf:
        assert zf.namelist() == ["main.sl", "slang.toml"]


def test_publish_and_list_registry(tmp_path):
    reg = tmp_path / "registry"
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    manifest(pkg / "slang.toml", "demo", "1.2.0")
    (pkg / "main.sl").write_text("module demo\n", encoding="utf-8")
    row = publish_package(pkg, reg)
    assert row["name"] == "demo"
    assert registry_list(reg)[0]["version"] == "1.2.0"


def test_install_transitive_registry_dependencies_and_lock(tmp_path):
    reg = tmp_path / "registry"
    base = tmp_path / "base"
    mid = tmp_path / "mid"
    for p in (base, mid):
        p.mkdir()
    manifest(base / "slang.toml", "base", "2.1.0")
    (base / "value.sl").write_text("module base\n", encoding="utf-8")
    manifest(mid / "slang.toml", "mid", "1.2.0", 'base = { path = "../base", version = "^2.0.0" }\n')
    (mid / "value.sl").write_text("module mid\n", encoding="utf-8")
    publish_package(base, reg)
    publish_package(mid, reg)

    app = tmp_path / "app"
    app.mkdir()
    (app / "src").mkdir()
    manifest(app / "slang.toml", "app", "0.1.0")
    result = install_package(app, "mid", "^1.0.0", reg)
    assert [x["name"] for x in result["installed"]] == ["base", "mid"]
    assert (app / "packages" / "mid" / "slang.toml").is_file()
    assert (app / "packages" / "base" / "slang.toml").is_file()

    installed_mid = (app / "packages" / "mid" / "slang.toml").read_text(encoding="utf-8")
    assert 'base = { path = "../base", version = "^2.0.0" }' in installed_mid
    app_manifest = (app / "slang.toml").read_text(encoding="utf-8")
    assert 'mid = { path = "packages/mid", version = "1.2.0" }' in app_manifest

    data = write_lock(app)
    assert [p["name"] for p in data["packages"]] == ["app", "base", "mid"]
    assert [p["version"] for p in resolve_dependencies(app)["packages"]] == ["0.1.0", "2.1.0", "1.2.0"]
