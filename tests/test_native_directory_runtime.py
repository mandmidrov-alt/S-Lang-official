import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_native_directory_runtime(tmp_path):
    work = tmp_path / "workspace"
    work.mkdir()
    (work / "b.txt").write_text("b", encoding="utf-8")
    (work / "a.txt").write_text("a", encoding="utf-8")
    source = tmp_path / "directory.sl"
    source.write_text(
        'let names = list_directory("workspace")\n'
        'show names\n'
        'let made = make_directory("created")\n'
        'let present = is_directory("created")\n'
        'let removed = remove_directory("created")\n'
        'let absent = not exists("created")\n'
        'show made\n'
        'show present\n'
        'show removed\n'
        'show absent\n',
        encoding="utf-8",
    )
    out = tmp_path / "directory"
    built = subprocess.run(
        [sys.executable, "-m", "slang.cli", "build", str(source), "-o", str(out), "--backend", "native"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert built.returncode == 0, built.stderr
    run = subprocess.run([str(out)], cwd=tmp_path, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert run.stdout.splitlines() == ["a.txt", "b.txt", "true", "true", "true", "true"]
    assert not (tmp_path / "created").exists()
