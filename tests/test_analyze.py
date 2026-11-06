from pathlib import Path
import subprocess, sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'examples' / 'two_body.sl'

def test_analyze_reports_semantics():
    out = subprocess.check_output([sys.executable, '-m', 'slang.cli', 'analyze', str(SRC)], cwd=ROOT, text=True)
    assert 'source_lines = 9' in out
    assert 'domains = physics' in out
    assert 'simulate.gravity' in out
    assert 'deterministic = yes' in out
    assert 'ai_runtime_dependency = no' in out
