from slang.core import parse, validate
from slang.mlir_backend import lower_execution_ir_to_mlir


def test_mlir_uses_one_schema_transform_for_direct_and_computed_fields():
    src='''
record Person:
    name: Text
    age: Number
    active: Boolean
    score: Number

record Final:
    ok: Boolean
    value: Number
    label: Text

let people = [Person("Alice", 20, true, 90), Person("Bob", 30, false, 70)]
final = people map Final(row.active, row.score - row.age, row.name)
show final
'''
    p=parse(src); validate(p)
    text=lower_execution_ir_to_mlir(p.ast)
    body=text[text.index('func.func @slang_program'):]
    assert '@slang_record_mixed_map_to_schema_expr' in body
    assert '@slang_record_mixed_project_fields' not in body
    # Direct source-field copies are encoded by the unified transform's opcode 26.
    assert 'arith.constant 26 : i64' in body
