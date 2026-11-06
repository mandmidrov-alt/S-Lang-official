from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def build_run(tmp_path, source):
    src = tmp_path / 'group_multi.sl'; out = tmp_path / 'group_multi'
    src.write_text(source, encoding='utf-8')
    p = subprocess.run([sys.executable, '-m', 'slang.cli', 'build', str(src), '-o', str(out), '--backend', 'native'], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()

def test_native_csv_group_multi_numeric_single_traversal(tmp_path):
    csv = tmp_path / 'people.csv'
    csv.write_text('team,role,score\nA,engineer,10\nB,engineer,5\nA,designer,20\nB,engineer,15\nA,engineer,30\n', encoding='utf-8')
    source = f'''record Scored:
    team: Text
    score: Number
let rows = read_csv("{csv.as_posix()}")
selected = rows where item.role == "engineer"
scored = selected map Scored(row.team, to_number(row.score))
sums = group_sum(scored, "team", "score")
counts = group_count(scored, "team")
avgs = group_average(scored, "team", "score")
show sums
show counts
show avgs
'''
    assert build_run(tmp_path, source) == '\n'.join([
        '[row(key=A, sum=40), row(key=B, sum=20)]',
        '[row(key=A, count=2), row(key=B, count=2)]',
        '[row(key=A, average=20), row(key=B, average=10)]',
    ])
