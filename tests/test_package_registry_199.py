import json
import pytest
from slang.project import check_package, package_archive, publish_package, registry_list, remove_registry_package


def manifest(path, name, version, deps=""):
    path.write_text(f'[package]\nname = "{name}"\nversion = "{version}"\nsource_roots = ["."]\n\n[dependencies]\n{deps}', encoding='utf-8')


def test_package_check_and_registry_metadata(tmp_path):
    reg = tmp_path / 'registry'
    pkg = tmp_path / 'pkg'; pkg.mkdir()
    manifest(pkg/'slang.toml', 'demo', '1.2.0', 'base = { path = "../base", version = "^2.0.0" }\n')
    (pkg/'main.sl').write_text('module demo\n', encoding='utf-8')
    result = check_package(pkg)
    assert result['status'] == 'valid'
    row = publish_package(pkg, reg)
    meta = json.loads((reg/'demo'/'1.2.0'/'package.json').read_text())
    assert meta['name'] == 'demo' and len(meta['sha256']) == 64
    assert registry_list(reg)[0]['sha256'] == meta['sha256']


def test_publish_requires_force_to_replace(tmp_path):
    reg=tmp_path/'registry'; pkg=tmp_path/'pkg'; pkg.mkdir()
    manifest(pkg/'slang.toml','demo','1.0.0'); (pkg/'main.sl').write_text('module demo\n')
    publish_package(pkg, reg)
    with pytest.raises(ValueError, match='already exists'):
        publish_package(pkg, reg)
    assert publish_package(pkg, reg, force=True)['replaced'] is True


def test_registry_remove(tmp_path):
    reg=tmp_path/'registry'; pkg=tmp_path/'pkg'; pkg.mkdir()
    manifest(pkg/'slang.toml','demo','1.0.0'); (pkg/'main.sl').write_text('module demo\n')
    publish_package(pkg, reg)
    assert remove_registry_package('demo','1.0.0',reg)['removed']
    assert registry_list(reg) == []
