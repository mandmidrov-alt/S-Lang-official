from slang.core import parse, validate
from slang.mlir_backend import lower_execution_ir_to_mlir


def test_mlir_mixed_record_literal_filter_and_map_use_typed_abi():
    src='''
record Person:
    name: Text
    age: Number
    active: Boolean
    score: Number

let people = [Person("Alice", 20, true, 90), Person("Bob", 30, false, 70), Person("Alice", 40, true, 95)]
selected = people where row.active and row.name == "Alice" and row.score > row.age * 2
updated = selected map Person(row.name, row.age + 1, not row.active, row.score)
show updated
'''
    p=parse(src); validate(p)
    text=lower_execution_ir_to_mlir(p.ast)
    assert '@slang_record_mixed_new_flat' in text
    assert '@slang_record_mixed_filter_expr' in text
    assert '@slang_record_mixed_map_fields_expr' in text
    assert '@slang_record_f64_map_fields_expr(' not in text[text.index('func.func @slang_program'):]
    assert 'memref<6xi8>' in text
    assert '== "Alice"' not in text
