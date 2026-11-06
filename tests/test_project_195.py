import pytest
from slang.project import resolve_dependencies, resolve_import, write_lock, lock_path
from slang.core import parse_file, run, show_expr_value


def write_manifest(path, name, version, deps=''):
    path.write_text(f'''[package]\nname = "{name}"\nversion = "{version}"\nsource_roots = ["src"]\n\n[dependencies]\n{deps}''', encoding='utf-8')


def test_transitive_dependency_resolution_and_import(tmp_path):
    root = tmp_path / 'app'; root.mkdir()
    write_manifest(root / 'slang.toml', 'app', '0.1.0', 'mid = "../mid"\n')
    mid = tmp_path / 'mid'; mid.mkdir()
    write_manifest(mid / 'slang.toml', 'mid', '1.2.0', 'base = { path = "../base", version = "^2.0.0" }\n')
    base = tmp_path / 'base'; base.mkdir()
    write_manifest(base / 'slang.toml', 'base', '2.3.1')
    (base / 'value.sl').write_text('module base\nexport double\nfunction double(x: Number) -> Number:\n    return x * 2\n', encoding='utf-8')
    (mid / 'value.sl').write_text('module mid\nimport base.value as b\nexport twice\nfunction twice(x: Number) -> Number:\n    return b.double(x)\n', encoding='utf-8')
    (root / 'src').mkdir()
    main = root / 'src' / 'main.sl'
    main.write_text('module app\nimport mid.value as m\nlet x = m.twice(21)\nshow x\n', encoding='utf-8')
    graph = resolve_dependencies(root)
    assert [p['name'] for p in graph['packages']] == ['app', 'base', 'mid']
    assert resolve_import(root / 'src', 'mid.value') == (mid / 'value.sl').resolve()
    assert resolve_import(mid, 'base.value') == (base / 'value.sl').resolve()
    p = parse_file(main); run(p)
    assert show_expr_value(p, p.show_exprs[0]) == '42'


def test_dependency_version_constraint_rejects_incompatible(tmp_path):
    root = tmp_path / 'app'; root.mkdir()
    write_manifest(root / 'slang.toml', 'app', '0.1.0', 'dep = { path = "../dep", version = "^2.0.0" }\n')
    dep = tmp_path / 'dep'; dep.mkdir()
    write_manifest(dep / 'slang.toml', 'dep', '1.5.0')
    with pytest.raises(ValueError, match='requires version'):
        resolve_dependencies(root)


def test_dependency_cycle_is_reported(tmp_path):
    a = tmp_path / 'a'; b = tmp_path / 'b'; a.mkdir(); b.mkdir()
    write_manifest(a / 'slang.toml', 'a', '1.0.0', 'b = "../b"\n')
    write_manifest(b / 'slang.toml', 'b', '1.0.0', 'a = "../a"\n')
    with pytest.raises(ValueError, match='cyclic package dependency'):
        resolve_dependencies(a)


def test_exact_and_tilde_constraints(tmp_path):
    root = tmp_path / 'app'; root.mkdir()
    write_manifest(root / 'slang.toml', 'app', '0.1.0', 'dep = { path = "../dep", version = "~1.4.0" }\n')
    dep = tmp_path / 'dep'; dep.mkdir()
    write_manifest(dep / 'slang.toml', 'dep', '1.4.9')
    resolve_dependencies(root)


def test_lock_file_is_created_and_reused(tmp_path):
    root = tmp_path / "app"; root.mkdir()
    write_manifest(root / 'slang.toml', 'app', '0.1.0', 'dep = { path = "../dep", version = "^1.0.0" }\n')
    dep = tmp_path / "dep"; dep.mkdir()
    write_manifest(dep / 'slang.toml', 'dep', '1.4.2')
    data = write_lock(root)
    assert lock_path(root).is_file()
    assert [p["name"] for p in data["packages"]] == ["app", "dep"]
    locked = resolve_dependencies(root)
    assert [p["version"] for p in locked["packages"]] == ["0.1.0", "1.4.2"]

    # A fresh resolver would see the new version, but the lock keeps the graph pinned.
    write_manifest(dep / 'slang.toml', 'dep', '1.4.9')
    with pytest.raises(ValueError, match='changed version|manifest changed'):
        resolve_dependencies(root)


def test_lock_rejects_changed_constraint(tmp_path):
    root = tmp_path / "app"; root.mkdir()
    write_manifest(root / 'slang.toml', 'app', '0.1.0', 'dep = { path = "../dep", version = "^1.0.0" }\n')
    dep = tmp_path / "dep"; dep.mkdir()
    write_manifest(dep / 'slang.toml', 'dep', '1.4.2')
    write_lock(root)
    write_manifest(root / 'slang.toml', 'app', '0.1.0', 'dep = { path = "../dep", version = "^2.0.0" }\n')
    with pytest.raises(ValueError, match='manifest changed'):
        resolve_dependencies(root)


def test_lock_can_be_checked_without_rewriting(tmp_path):
    root = tmp_path / "app"; root.mkdir()
    write_manifest(root / 'slang.toml', 'app', '0.1.0', 'dep = "../dep"\n')
    dep = tmp_path / "dep"; dep.mkdir()
    write_manifest(dep / 'slang.toml', 'dep', '1.0.0')
    write_lock(root)
    before = lock_path(root).read_bytes()
    assert resolve_dependencies(root)["packages"][0]["name"] == "app"
    assert lock_path(root).read_bytes() == before


def test_lock_rejects_changed_source(tmp_path):
    root = tmp_path / "app"; root.mkdir()
    write_manifest(root / 'slang.toml', 'app', '0.1.0')
    src = root / 'src'; src.mkdir()
    main = src / 'main.sl'
    main.write_text('module app\nlet x = 1\nshow x\n', encoding='utf-8')
    write_lock(root)
    assert resolve_dependencies(root)["packages"][0]["name"] == "app"
    main.write_text('module app\nlet x = 2\nshow x\n', encoding='utf-8')
    with pytest.raises(ValueError, match='source changed'):
        resolve_dependencies(root)


def test_lock_rejects_added_and_removed_source(tmp_path):
    root = tmp_path / "app"; root.mkdir()
    write_manifest(root / 'slang.toml', 'app', '0.1.0')
    src = root / 'src'; src.mkdir()
    main = src / 'main.sl'
    main.write_text('module app\n', encoding='utf-8')
    write_lock(root)
    extra = src / 'extra.sl'
    extra.write_text('module extra\n', encoding='utf-8')
    with pytest.raises(ValueError, match='source changed'):
        resolve_dependencies(root)
    extra.unlink()
    main.unlink()
    with pytest.raises(ValueError, match='source changed'):
        resolve_dependencies(root)
