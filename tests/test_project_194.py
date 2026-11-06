from pathlib import Path
from slang.core import parse_file, run, show_expr_value
from slang.project import find_root, load_manifest, resolve_import

def test_project_manifest_resolves_source_root(tmp_path):
    (tmp_path/'slang.toml').write_text('''[package]\nname = "demo"\nversion = "0.1.0"\nsource_roots = ["src", "lib"]\n''', encoding='utf-8')
    (tmp_path/'lib'/'util').mkdir(parents=True)
    (tmp_path/'lib'/'util'/'text.sl').write_text('''module util.text\nexport double\nfunction double(x: Number) -> Number:\n    return x * 2\n''', encoding='utf-8')
    main = tmp_path/'src'/'main.sl'; main.parent.mkdir()
    main.write_text('''module demo\nimport util.text as text\nlet value = text.double(21)\nshow value\n''', encoding='utf-8')
    assert find_root(main) == tmp_path
    assert resolve_import(main.parent, 'util.text') == (tmp_path/'lib'/'util'/'text.sl').resolve()
    p = parse_file(main); run(p)
    assert show_expr_value(p, p.show_exprs[0]) == '42'

def test_dependency_package_path_resolution(tmp_path):
    (tmp_path/'slang.toml').write_text('''[package]\nname = "app"\nversion = "0.1.0"\nsource_roots = ["src"]\n\n[dependencies]\nmathkit = "packages/mathkit"\n''', encoding='utf-8')
    dep = tmp_path/'packages'/'mathkit'; dep.mkdir(parents=True)
    (dep/'vector.sl').write_text('module vector\n', encoding='utf-8')
    assert resolve_import(tmp_path/'src', 'mathkit.vector') == (dep/'vector.sl').resolve()
