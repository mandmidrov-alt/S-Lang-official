import math,sys
sys.path.insert(0,'.')
from slang.core import parse,validate,run,ParseError

SRC=open('examples/two_body.sl').read()

def test_parse():
    p=parse(SRC); validate(p)
    assert p.simulation==("earth","sun",86400.0,60.0)

def test_physics_result():
    p=run(parse(SRC)); earth=next(b for b in p.bodies if b.name=='earth')
    assert abs(earth.fields['position'].value-152194895551.0479)<1e-3
    assert abs(earth.fields['velocity'].value-30283.78894717536)<1e-9

def test_unit_error():
    bad=SRC.replace('velocity 29780 mps','velocity 29780 kg')
    try: validate(parse(bad))
    except TypeError: return
    assert False

def test_missing_physics():
    bad=SRC.replace('physics gravity\n','')
    try: validate(parse(bad))
    except TypeError: return
    assert False


def test_mlir_lowering_is_loop_based_and_standard_dialect_only():
    from slang.core import mlir
    text=mlir(parse(SRC))
    assert "scf.for" in text
    assert "arith.mulf" in text
    assert "func.call @simulate" in text
    assert '"slang.' not in text
    assert "scf.yield" in text
