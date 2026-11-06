from slang.core import parse, validate
from slang.mlir_backend import lower_execution_ir_to_mlir


def test_mlir_uses_direct_mixed_projection_for_field_selection_and_reordering():
    src='''
record Person:
    name: Text
    age: Number
    active: Boolean
    score: Number

record Summary:
    label: Text
    value: Number
    ok: Boolean

let people = [Person("Ada", 20, true, 90), Person("Bob", 30, false, 70)]
summaries = people map Summary(row.name, row.score, row.active)
show summaries
'''
    p=parse(src); validate(p)
    text=lower_execution_ir_to_mlir(p.ast)
    assert '@slang_record_mixed_project_fields' in text
    body=text[text.index('func.func @slang_program'):]
    assert '@slang_record_mixed_map_to_schema_expr' not in body
