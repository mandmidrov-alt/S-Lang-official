from pathlib import Path
import subprocess, sys
ROOT = Path(__file__).resolve().parents[1]

def build_run(tmp_path, source):
    src=tmp_path/'group_ext.sl'; out=tmp_path/'group_ext'
    src.write_text(source, encoding='utf-8')
    p=subprocess.run([sys.executable,'-m','slang.cli','build',str(src),'-o',str(out),'--backend','native'],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    r=subprocess.run([str(out)],cwd=ROOT,text=True,capture_output=True)
    assert r.returncode==0,r.stderr
    return r.stdout.strip()

def source_for(csv):
    return f'''record Scored:
    team: Text
    score: Number
let rows = read_csv("{csv.as_posix()}")
scored = rows map Scored(row.team, to_number(row.score))
sums = group_sum(scored, "team", "score")
counts = group_count(scored, "team")
avgs = group_average(scored, "team", "score")
mins = group_min(scored, "team", "score")
maxs = group_max(scored, "team", "score")
show sums
show counts
show avgs
show mins
show maxs
'''

def test_native_group_min_max_multi(tmp_path):
    csv=tmp_path/'people.csv'
    csv.write_text('team,score\nA,10\nB,5\nA,20\nB,15\nA,30\n',encoding='utf-8')
    assert build_run(tmp_path,source_for(csv)) == '\n'.join([
        '[row(key=A, sum=60), row(key=B, sum=20)]',
        '[row(key=A, count=3), row(key=B, count=2)]',
        '[row(key=A, average=20), row(key=B, average=10)]',
        '[row(key=A, min=10), row(key=B, min=5)]',
        '[row(key=A, max=30), row(key=B, max=15)]',
    ])

def test_reference_group_min_max():
    from slang.stdlib.aggregate import group_min, group_max
    people=[{"team":"A","score":10},{"team":"B","score":5},{"team":"A","score":20},{"team":"B","score":15},{"team":"A","score":30}]
    assert group_min(people,"team","score") == [{"key":"A","min":10},{"key":"B","min":5}]
    assert group_max(people,"team","score") == [{"key":"A","max":30},{"key":"B","max":15}]
