from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
def build_run(tmp_path, source):
    src=tmp_path/'group_numeric.sl'; out=tmp_path/'group_numeric'
    src.write_text(source,encoding='utf-8')
    p=subprocess.run([sys.executable,'-m','slang.cli','build',str(src),'-o',str(out),'--backend','native'],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    r=subprocess.run([str(out)],cwd=ROOT,text=True,capture_output=True)
    assert r.returncode==0,r.stderr
    return r.stdout.strip()
def test_native_csv_group_sum_after_explicit_numeric_record_map(tmp_path):
    csv=tmp_path/'people.csv'; csv.write_text('team,score\nA,10\nB,5\nA,20\nB,15\nA,30\n',encoding='utf-8')
    assert build_run(tmp_path,f'''record Scored:\n    team: Text\n    score: Number\nlet rows = read_csv("{csv.as_posix()}")\nscored = rows map Scored(row.team, to_number(row.score))\nresult = group_sum(scored, "team", "score")\nshow result\n''') == '[row(key=A, sum=60), row(key=B, sum=20)]'
def test_native_csv_group_average_after_explicit_numeric_record_map(tmp_path):
    csv=tmp_path/'people.csv'; csv.write_text('team,score\nA,10\nB,5\nA,20\nB,15\nA,30\n',encoding='utf-8')
    assert build_run(tmp_path,f'''record Scored:\n    team: Text\n    score: Number\nlet rows = read_csv("{csv.as_posix()}")\nscored = rows map Scored(row.team, to_number(row.score))\nresult = group_average(scored, "team", "score")\nshow result\n''') == '[row(key=A, average=20), row(key=B, average=10)]'
