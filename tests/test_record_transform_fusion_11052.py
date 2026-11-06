from slang.core import parse, validate
from slang.optimizer import optimize_program
from slang.mlir_backend import lower_execution_ir_to_mlir
from slang.execution_ir import build_execution_ir


def _program():
    src = '''
record Person:
    name: Text
    age: Number
    active: Boolean
    score: Number

record Summary:
    label: Text
    value: Number
    ok: Boolean

record Final:
    text: Text
    amount: Number
    enabled: Boolean

let people = [Person("Ada", 20, true, 90), Person("Bob", 30, false, 70)]
summaries = people map Summary(row.name, row.score - row.age, row.active)
finals = summaries map Final(row.label, row.value + 1, not row.ok)
show finals
'''
    p = parse(src)
    validate(p)
    return p


def test_optimizer_fuses_schema_changing_record_transforms():
    p = _program()
    report = optimize_program(p)
    assert report.record_transform_fusions == 1
    assert len(p.ast.maps) == 1
    assert p.ast.maps[0].source == 'people'
    assert p.ast.maps[0].result == 'finals'
    assert p.ast.maps[0].expr.name == 'Final'


def test_fused_record_transform_lowers_as_one_mixed_schema_transform():
    p = _program()
    optimize_program(p)
    text = lower_execution_ir_to_mlir(p.ast)
    body = text[text.index('func.func @slang_program'):]
    assert body.count('@slang_record_mixed_map_to_schema_expr') == 1
