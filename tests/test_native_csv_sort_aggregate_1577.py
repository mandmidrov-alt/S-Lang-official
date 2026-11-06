import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def build_run(tmp_path, source):
    src = tmp_path / "program.sl"
    out = tmp_path / "program"
    src.write_text(source, encoding="utf-8")
    p = subprocess.run([sys.executable, "-m", "slang.cli", "build", str(src), "-o", str(out)], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()

def test_native_csv_materialized_sort_ascending(tmp_path):
    csv = tmp_path / "people.csv"
    csv.write_text("team,score\nB,20\nA,30\nA,10\n", encoding="utf-8")
    source = 'let rows = read_csv("{}")\nsorted = rows |> sort by row.score asc\nshow sorted\n'.format(csv.as_posix())
    out = build_run(tmp_path, source)
    assert out == "[row(team=A, score=10), row(team=B, score=20), row(team=A, score=30)]"

def test_native_csv_materialized_sort_descending_is_stable(tmp_path):
    csv = tmp_path / "people.csv"
    csv.write_text("team,score\nA,20\nB,20\nC,10\n", encoding="utf-8")
    source = 'let rows = read_csv("{}")\nsorted = rows |> sort by row.score desc\nshow sorted\n'.format(csv.as_posix())
    out = build_run(tmp_path, source)
    assert out == "[row(team=A, score=20), row(team=B, score=20), row(team=C, score=10)]"
