import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_native_run_process_returns_exit_stdout_stderr(tmp_path):
    src = tmp_path / 'process.sl'
    src.write_text('let result = run_process("printf \'hello\\n\'; printf \'error\\n\' 1>&2; exit 3")\nshow result\n', encoding='utf-8')
    out = tmp_path / ('process.exe' if sys.platform.startswith('win') else 'process')
    p = subprocess.run([sys.executable, '-m', 'slang.cli', 'build', str(src), '-o', str(out)], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], cwd=tmp_path, text=True, capture_output=True)
    assert r.returncode == 0
    assert '3' in r.stdout
    assert 'hello' in r.stdout
    assert 'error' in r.stdout
