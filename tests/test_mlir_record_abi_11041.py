from slang.core import parse, validate
from slang.mlir_backend import lower_execution_ir_to_mlir


def test_mlir_declares_record_f64_abi_for_numeric_schema():
    src = '''
record Point:
    x: Number
    y: Number
let points = [Point(1, 10), Point(2, 20)]
selected = points where row.x >= 2
updated = selected map Point(row.x + 1, row.y)
show updated
'''
    p = parse(src); validate(p)
    text = lower_execution_ir_to_mlir(p.ast)
    assert '@slang_record_f64_new' in text
    assert '@slang_record_f64_filter' in text
    assert '@slang_record_f64_map_field' in text
    assert 'record-f64-abi' in text
