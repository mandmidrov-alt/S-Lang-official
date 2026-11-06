from pathlib import Path

from slang.core import parse, run, validate


def test_path_stdlib_runtime():
    source = '''
result = join_path("data", "people.csv")
name = basename(result)
dir = dirname(result)
ext = extension(result)
norm = normalize_path("data/./people.csv")
'''
    p = parse(source)
    validate(p)
    run(p)
    assert p._bindings["result"] == "data/people.csv"
    assert p._bindings["name"] == "people.csv"
    assert p._bindings["dir"] == "data"
    assert p._bindings["ext"] == ".csv"
    assert p._bindings["norm"] == "data/people.csv"


def test_filesystem_stdlib_runtime(tmp_path):
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / "a.txt").write_text("abc", encoding="utf-8")
    source = f'''
size = file_size("{tmp_path / 'a.txt'}")
file = is_file("{tmp_path / 'a.txt'}")
directory = is_directory("{tmp_path}")
items = list_directory("{tmp_path}")
'''
    p = parse(source)
    validate(p)
    run(p)
    assert p._bindings["size"] == 3
    assert p._bindings["file"] is True
    assert p._bindings["directory"] is True
    assert p._bindings["items"] == ["a.txt", "b.txt"]
