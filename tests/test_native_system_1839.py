from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("clang") is None, reason="clang is required for native executable tests")
def test_native_write_lines_and_path_runtime(tmp_path):
    source = tmp_path / "main.sl"
    source.write_text(
        'let lines = read_lines("input.txt")\n'
        'let ok = write_lines("output.txt", lines)\n'
        'let base = basename("workspace/data.txt")\n'
        'let directory = dirname("workspace/data.txt")\n'
        'let ext = extension("workspace/data.txt")\n'
        'let joined = join_path("workspace", "data.txt")\n'
        'let normalized = normalize_path("workspace//data.txt")\n'
        'show ok\nshow base\nshow directory\nshow ext\nshow joined\nshow normalized\n',
        encoding="utf-8",
    )
    (tmp_path / "input.txt").write_text("one\ntwo\n", encoding="utf-8")
    exe = tmp_path / ("program.exe" if sys.platform == "win32" else "program")
    subprocess.run(
        [sys.executable, str(ROOT / "build_native.py"), str(source), "-o", str(exe)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    result = subprocess.run([str(exe)], cwd=tmp_path, check=True, capture_output=True, text=True)
    assert result.stdout.splitlines() == [
        "true", "data.txt", "workspace", ".txt", "workspace/data.txt", "workspace/data.txt"
    ]
    assert (tmp_path / "output.txt").read_text(encoding="utf-8") == "one\ntwo\n"
