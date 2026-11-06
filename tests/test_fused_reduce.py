import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_fused_filter_map_reduce_selects_strategy():
    p = subprocess.run([sys.executable, '-m', 'slang.cli', 'strategies', 'examples/fused_reduce.sl'], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    assert 'total#1: fused-filter-map-reduce' in p.stdout

def test_fused_filter_map_reduce_emits_one_pass_native_ir():
    p = subprocess.run([sys.executable, '-m', 'slang.cli', 'emit-llvm', 'examples/fused_reduce.sl'], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    assert 'slang-fused-reduce' in p.stdout
    assert '@data_numbers_value' in p.stdout
    assert 'alloca [' not in p.stdout
    assert 'fadd double %cur_acc' in p.stdout

def test_fused_filter_map_reduce_build_executes(tmp_path):
    out = tmp_path / 'fused_reduce'
    p = subprocess.run([sys.executable, '-m', 'slang.cli', 'build', 'examples/fused_reduce.sl', '-o', str(out)], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    run = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True)
    assert run.returncode == 0
    assert run.stdout.strip() == '18'
