from slang.core import parse, validate
from slang.mlir_backend import lower_execution_ir_to_mlir


def test_mlir_declares_schema_preserving_record_field_mask():
    src = '''
record Person:
    id: Number
    name: Text
    score: Number
let people = [Person(1, "A", 5), Person(2, "B", 7)]
selected = people where row.id > 0
show selected
'''
    module = parse(src)
    validate(module)
    text = lower_execution_ir_to_mlir(module.ast)
    assert '@slang_record_mixed_mask_fields' in text
