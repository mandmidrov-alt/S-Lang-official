from slang.core import parse, validate
from slang.mlir_backend import lower_execution_ir_to_mlir


def test_mlir_mixed_record_schema_change_uses_typed_target_abi():
    src='''
record Person:
    name: Text
    age: Number
    active: Boolean
    score: Number

record Summary:
    label: Text
    value: Number

let people = [Person("Alice", 20, true, 90), Person("Bob", 30, false, 70)]
summaries = people map Summary(row.name, row.score - row.age)
show summaries
'''
    p=parse(src); validate(p)
    text=lower_execution_ir_to_mlir(p.ast)
    assert '@slang_record_mixed_map_to_schema_expr' in text
    assert 'mixed_schema_types' in text
    assert '@slang_record_f64_map_fields_expr' not in text[text.index('func.func @slang_program'):]
