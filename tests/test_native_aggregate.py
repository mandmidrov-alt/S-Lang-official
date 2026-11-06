import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_native_sum(tmp_path):
    src=tmp_path/'sum.sl'; out=tmp_path/'sum'
    src.write_text('''data numbers:\n    a value 1\n    b value 2\n    c value 3\n\ntotal = numbers sum value\nshow total\n''')
    p=subprocess.run([sys.executable,'-m','slang.cli','build',str(src),'-o',str(out)],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    r=subprocess.run([str(out)],text=True,capture_output=True)
    assert r.returncode==0,r.stderr
    assert r.stdout.strip() == '6'

def test_native_filter_map_sum(tmp_path):
    src=tmp_path/'sum.sl'; out=tmp_path/'sum'
    src.write_text('''data numbers:\n    a value 1\n    b value 2\n    c value 3\n    d value 4\n\nfiltered = numbers where value >= 2\nscaled = filtered map value * 2\ntotal = scaled sum item\nshow total\n''')
    p=subprocess.run([sys.executable,'-m','slang.cli','build',str(src),'-o',str(out)],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    r=subprocess.run([str(out)],text=True,capture_output=True)
    assert r.returncode==0,r.stderr
    assert r.stdout.strip() == '18'

def test_native_aggregate_has_real_loop(tmp_path):
    src=tmp_path/'avg.sl'
    src.write_text('''data numbers:\n    a value 1\n    b value 2\n    c value 3\n\navg = numbers average value\nshow avg\n''')
    p=subprocess.run([sys.executable,'-m','slang.cli','emit-llvm',str(src)],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    assert 'label %agg_loop' in p.stdout
    assert 'fdiv double' in p.stdout

def test_native_count_max_min(tmp_path):
    for op, expected in [('count','3'), ('max','7'), ('min','2')]:
        src=tmp_path/f'{op}.sl'; out=tmp_path/op
        expr='' if op=='count' else ' value'
        src.write_text(f'''data numbers:\n    a value 2\n    b value 7\n    c value 4\n\nresult = numbers {op}{expr}\nshow result\n''')
        p=subprocess.run([sys.executable,'-m','slang.cli','build',str(src),'-o',str(out)],cwd=ROOT,text=True,capture_output=True)
        assert p.returncode==0,p.stderr
        r=subprocess.run([str(out)],text=True,capture_output=True)
        assert r.returncode==0,r.stderr
        assert r.stdout.strip() == expected

def test_native_filter_map_aggregate_is_fused(tmp_path):
    src=tmp_path/'fused.sl'
    src.write_text('''data numbers:\n    a value 1\n    b value 2\n    c value 3\n    d value 4\n\nfiltered = numbers where value >= 2\nscaled = filtered map value * 2\ntotal = scaled sum item\nshow total\n''')
    p=subprocess.run([sys.executable,'-m','slang.cli','emit-llvm',str(src)],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    # Fusion must not allocate an intermediate collection buffer.
    assert 'slang-fused-aggregate' in p.stdout
    assert 'alloca [4 x double]' not in p.stdout
    assert 'alloca [3 x double]' not in p.stdout
    assert 'label %loop' in p.stdout
    assert 'fcmp oge double' in p.stdout
    assert 'fmul double' in p.stdout
    assert 'fadd double' in p.stdout
