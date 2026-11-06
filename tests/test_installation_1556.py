from pathlib import Path

from slang.project import init_project


def test_init_project_creates_minimal_runnable_project(tmp_path):
    root = init_project(tmp_path / "hello-app", name="hello-app", version="0.1.0")
    assert (root / "slang.toml").is_file()
    entry = root / "src" / "main.sl"
    assert entry.is_file()
    assert "let value = 0" in entry.read_text(encoding="utf-8")
    assert (root / "README.md").is_file()


def test_init_project_refuses_to_overwrite(tmp_path):
    root = init_project(tmp_path / "hello-app")
    try:
        init_project(root)
    except ValueError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("expected init_project to refuse an existing project")


def test_runtime_is_bundled_with_package():
    assert Path(__file__).resolve().parents[1].joinpath("slang", "slang_runtime.c").is_file()
