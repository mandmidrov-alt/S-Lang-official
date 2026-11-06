from pathlib import Path
import subprocess, sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'examples' / 'optimization.sl'

def test_optimizer_fuses_maps():
    out = subprocess.check_output([sys.executable, '-m', 'slang.cli', 'optimize', str(SRC)], cwd=ROOT, text=True)
    assert 'map_fusions = 1' in out
    assert 'total_transformations = 2' in out

def test_optimized_run_keeps_semantics():
    out = subprocess.check_output([sys.executable, '-m', 'slang.cli', 'run', str(SRC)], cwd=ROOT, text=True)
    assert out.strip() == '[3, 5, 7]'


def test_optimizer_does_not_self_fuse_reassigned_map():
    from slang.core import parse, validate, run
    p = parse("""
data people:
    Alice age 22 score 91
    Bob age 17 score 88
selected = people where age >= 18
selected sort by score desc
selected = selected map score
total = selected sum item
show total
""")
    validate(p)
    run(p)
    assert p._collections['selected'] == [91]
    assert p._collections['total'] == 91
