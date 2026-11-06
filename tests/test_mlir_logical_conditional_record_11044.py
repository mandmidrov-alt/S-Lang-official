from slang.core import parse, validate
from slang.mlir_backend import lower_execution_ir_to_mlir


def test_mlir_lowers_or_and_not_record_predicate_to_expression_abi():
    src = '''
record Person:
    age: Number
    score: Number

let people = [Person(20, 50), Person(30, 70), Person(40, 95)]
selected = people where not (row.age < 30) or row.score > row.age * 2
show selected
'''
    p = parse(src); validate(p)
    text = lower_execution_ir_to_mlir(p.ast)
    assert '@slang_record_f64_filter_expr' in text
    assert 'record-schema-storage' in text


def test_mlir_lowers_conditional_record_map_to_expression_abi():
    src = '''
record Person:
    age: Number
    score: Number

let people = [Person(20, 50), Person(30, 70)]
updated = people map Person(row.age, if row.score > 60 then row.score - row.age else row.score + row.age)
show updated
'''
    p = parse(src); validate(p)
    text = lower_execution_ir_to_mlir(p.ast)
    assert '@slang_record_f64_map_field_expr' in text
