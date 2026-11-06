import sys, subprocess
from pathlib import Path
sys.path.insert(0,'.')
from slang.core import parse, validate, llvm_ir

def test_llvm_has_real_loop_and_main():
    p=parse(Path('examples/two_body.sl').read_text()); validate(p)
    s=llvm_ir(p)
    assert 'define i32 @main()' in s
    assert 'phi double' in s
    assert 'fdiv double' in s
    assert 'icmp ult i64' in s

def test_native_build_and_output(tmp_path):
    src=Path('examples/two_body.sl')
    exe=tmp_path/'two_body'
    subprocess.run([sys.executable,'build_native.py',str(src),'-o',str(exe)],check=True)
    out=subprocess.check_output([str(exe)],text=True)
    assert 'earth.position' in out
    assert 'earth.velocity' in out
    assert '152194895551' in out
