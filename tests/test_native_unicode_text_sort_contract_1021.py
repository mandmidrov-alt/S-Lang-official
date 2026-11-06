import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_and_run(tmp_path, source):
    src = tmp_path / "unicode_sort.sl"
    exe = tmp_path / "unicode_sort"
    src.write_text(source, encoding="utf-8")
    build = subprocess.run(
        [sys.executable, "-m", "slang.cli", "build", str(src), "-o", str(exe), "--backend", "native"],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(exe)], cwd=ROOT, text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    return run.stdout.splitlines()


def test_native_sort_orders_unicode_text_keys(tmp_path):
    out = build_and_run(tmp_path, '''
record Item:
    key: Text
    label: Text

let items = [Item("я", "last"), Item("а", "first"), Item("м", "middle")]
ordered = items sort by row.key asc
labels = ordered map row.label
show labels
''')
    assert out == ["first", "middle", "last"]


def test_native_sort_is_stable_for_equal_text_keys(tmp_path):
    out = build_and_run(tmp_path, '''
record Item:
    key: Text
    label: Text

let items = [Item("same", "first"), Item("same", "second"), Item("same", "third")]
ordered = items sort by row.key asc
labels = ordered map row.label
show labels
''')
    assert out == ["first", "second", "third"]


def test_native_sort_orders_unicode_text_keys_descending(tmp_path):
    out = build_and_run(tmp_path, '''
record Item:
    key: Text
    label: Text

let items = [Item("я", "last"), Item("а", "first"), Item("м", "middle")]
ordered = items sort by row.key desc
labels = ordered map row.label
show labels
''')
    assert out == ["last", "middle", "first"]


def test_native_sort_descending_is_stable_for_equal_text_keys(tmp_path):
    out = build_and_run(tmp_path, '''
record Item:
    key: Text
    label: Text

let items = [Item("same", "first"), Item("same", "second"), Item("same", "third")]
ordered = items sort by row.key desc
labels = ordered map row.label
show labels
''')
    assert out == ["first", "second", "third"]
