from pathlib import Path
import subprocess
import sys


def test_native_external_csv_pipeline_matches_interpreter(tmp_path):
    root = Path(__file__).resolve().parents[1]
    csv = tmp_path / "people.csv"
    csv.write_text(
        "name,age,score,role\n"
        "a,17,10,engineer\n"
        "b,18,20,engineer\n"
        "c,30,30,artist\n"
        "d,25,40,engineer\n",
        encoding="utf-8",
    )
    source = tmp_path / "main.sl"
    source.write_text(
        f'''let rows = read_csv("{csv}")\n'''
        'adults = rows where to_number(item.age) >= 18\n'
        'engineers = adults where item.role == "engineer"\n'
        'scores = engineers map to_number(item.score)\n'
        'total = scores reduce 0 with acc + item\n'
        'show total\n',
        encoding="utf-8",
    )
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = str(root)
    interp = subprocess.run([sys.executable, "-m", "slang.cli", "run", str(source)], cwd=root, env=env, text=True, capture_output=True, check=True)
    native = tmp_path / "native"
    subprocess.run([sys.executable, "-m", "slang.cli", "build", str(source), "-o", str(native), "--backend", "native"], cwd=root, env=env, text=True, capture_output=True, check=True)
    native_run = subprocess.run([str(native)], cwd=root, text=True, capture_output=True, check=True)
    assert interp.stdout.strip().endswith("60")
    assert native_run.stdout.strip() == "60"
