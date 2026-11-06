import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def build_run(tmp_path, source):
    src = tmp_path / 'program.sl'
    out = tmp_path / 'program'
    src.write_text(source, encoding='utf-8')
    p = subprocess.run([sys.executable, '-m', 'slang.cli', 'build', str(src), '-o', str(out)], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()


def test_native_csv_sort_then_sum_elides_ordered_stage(tmp_path):
    csv = tmp_path / 'people.csv'
    csv.write_text('team,score\nA,30\nB,10\nA,20\nB,40\n', encoding='utf-8')
    out = build_run(tmp_path, f'''let rows = read_csv("{csv.as_posix()}")
sorted = rows |> sort by row.score asc |> map to_number(item.score) |> sum item
show sorted
''')
    assert out == ['100']


def test_native_csv_filter_sort_average_matches_reference(tmp_path):
    csv = tmp_path / 'people.csv'
    csv.write_text('team,score\nA,30\nB,10\nA,20\nB,40\n', encoding='utf-8')
    out = build_run(tmp_path, f'''let rows = read_csv("{csv.as_posix()}")
result = rows |> where item.team == "A" |> sort by row.score desc |> map to_number(item.score) |> average item
show result
''')
    assert out == ['25']
