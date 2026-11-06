from slang.core import parse, validate
from slang.mlir_backend import lower_execution_ir_to_mlir


def test_mlir_uses_single_multi_field_record_map_abi():
    src='''
record Person:
    age: Number
    score: Number

let people = [Person(20, 50), Person(30, 70), Person(40, 95)]
updated = people map Person(row.age + 1, if row.score > 60 then row.score - row.age else row.score + row.age)
show updated
'''
    p=parse(src); validate(p)
    text=lower_execution_ir_to_mlir(p.ast)
    assert '@slang_record_f64_map_fields_expr' in text
    body = text[text.index('func.func @slang_program'): ]
    assert '@slang_record_f64_map_field_expr(' not in body
