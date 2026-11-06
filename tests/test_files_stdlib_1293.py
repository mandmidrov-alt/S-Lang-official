from pathlib import Path

from slang.stdlib.files import list_directories, list_files, remove_directory_tree
from slang.stdlib.catalog import entries
from slang.stdlib import list_directories as public_list_directories, list_files as public_list_files, remove_directory_tree as public_remove_directory_tree

def test_list_files_and_directories(tmp_path):
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "dir2").mkdir()
    (tmp_path / "dir1").mkdir()
    assert list_files(str(tmp_path)) == ["a.txt", "b.txt"]
    assert list_directories(str(tmp_path)) == ["dir1", "dir2"]

def test_remove_directory_tree(tmp_path):
    nested = tmp_path / "root" / "nested"
    nested.mkdir(parents=True)
    (nested / "x.txt").write_text("x", encoding="utf-8")
    assert remove_directory_tree(str(tmp_path / "root")) is True
    assert not (tmp_path / "root").exists()

def test_public_exports():
    assert public_list_files is list_files
    assert public_list_directories is list_directories
    assert public_remove_directory_tree is remove_directory_tree
    names = {e["name"] for e in entries()}
    assert {"list_files", "list_directories", "remove_directory_tree"} <= names

def test_empty_directory_lists(tmp_path):
    assert list_files(str(tmp_path)) == []
    assert list_directories(str(tmp_path)) == []

def test_tree_removal_nested_files(tmp_path):
    root = tmp_path / "tree"
    (root / "a" / "b").mkdir(parents=True)
    (root / "a" / "b" / "file.txt").write_text("data", encoding="utf-8")
    remove_directory_tree(str(root))
    assert not root.exists()
