from slang.core import parse, validate
from slang.mlir_backend import lower_execution_ir_to_mlir


def test_mlir_lowers_literal_record_source_to_real_record_abi():
    src = '''
record Person:
    age: Number
    score: Number

let people = [Person(20, 50), Person(30, 80), Person(40, 90)]
selected = people where row.age >= 30
show selected
'''
    p = parse(src); validate(p)
    text = lower_execution_ir_to_mlir(p.ast)
    assert '@slang_record_f64_new_flat' in text
    assert '@slang_record_f64_filter' in text
    assert '(i64, i64, f64, i32) -> i64' in text
    assert 'record_flat_' in text


def test_mlir_lowers_record_filter_then_field_map_as_runtime_chain():
    src = '''
record Person:
    age: Number
    score: Number

let people = [Person(20, 50), Person(30, 80), Person(40, 90)]
selected = people where row.age >= 30
updated = selected map Person(row.age + 1, row.score)
show updated
'''
    p = parse(src); validate(p)
    text = lower_execution_ir_to_mlir(p.ast)
    assert '@slang_record_f64_new_flat' in text
    assert '@slang_record_f64_filter' in text
    assert '@slang_record_f64_map_field' in text
    assert 'selected_1' in text
