from slang.core import parse, validate
from slang.mlir_backend import lower_execution_ir_to_mlir


def test_mlir_lowers_multifield_and_predicate_to_record_runtime_chain():
    src = '''
record Person:
    age: Number
    score: Number

let people = [Person(20, 50), Person(30, 70), Person(40, 95)]
selected = people where row.age >= 30 and row.score > row.age * 2
show selected
'''
    p = parse(src); validate(p)
    text = lower_execution_ir_to_mlir(p.ast)
    assert '@slang_record_f64_filter_field_compare' in text
    assert text.count('@slang_record_f64_filter(') >= 1
    assert '@slang_record_f64_new_flat' in text


def test_mlir_lowers_two_field_record_map_expression():
    src = '''
record Person:
    age: Number
    score: Number

let people = [Person(20, 50), Person(30, 70)]
updated = people map Person(row.age, row.score - row.age)
show updated
'''
    p = parse(src); validate(p)
    text = lower_execution_ir_to_mlir(p.ast)
    assert '@slang_record_f64_map_field_binary' in text
    assert '(i64, i64, i64, i32) -> i64' in text
