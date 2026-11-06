import sys
from pathlib import Path
sys.path.insert(0,'.')
from slang.core import parse, validate, slang_mlir

def test_high_level_slang_dialect_op():
    p=parse(Path('examples/two_body.sl').read_text()); validate(p)
    s=slang_mlir(p)
    assert 'slang.simulate_gravity' in s
    assert 'scf.for' not in s
    assert 'arith.constant' in s
