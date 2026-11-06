import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_and_run(tmp_path, source):
    src = tmp_path / "sort_edges.sl"
    exe = tmp_path / "sort_edges"
    src.write_text(source, encoding="utf-8")
    build = subprocess.run(
        [sys.executable, "-m", "slang.cli", "build", str(src), "-o", str(exe), "--backend", "native"],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(exe)], cwd=ROOT, text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    return run.stdout.splitlines()


def test_native_text_sort_empty_and_different_length_keys(tmp_path):
    out = build_and_run(tmp_path, '''
record Item:
    key: Text
    label: Text

let items = [Item("beta", "beta"), Item("", "empty"), Item("a", "a"), Item("alphabet", "alphabet")]
ordered = items sort by row.key asc
labels = ordered map row.label
show labels
''')
    assert out == ["empty", "a", "alphabet", "beta"]


def test_native_text_sort_mixed_case_uses_codepoint_order(tmp_path):
    out = build_and_run(tmp_path, '''
record Item:
    key: Text
    label: Text

let items = [Item("b", "lower-b"), Item("A", "upper-a"), Item("a", "lower-a"), Item("B", "upper-b")]
ordered = items sort by row.key asc
labels = ordered map row.label
show labels
''')
    assert out == ["upper-a", "upper-b", "lower-a", "lower-b"]
