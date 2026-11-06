from slang.core import parse, validate
from slang.mlir_backend import lower_execution_ir_to_mlir


def test_mlir_mixed_record_rich_expression_chain():
    src = '''
record Person:
    name: Text
    age: Number
    active: Boolean
    score: Number

record Labeled:
    label: Text
    value: Number
    ok: Boolean

record Final:
    label: Text
    value: Number
    status: Text
    ok: Boolean

let people = [Person("Alice", 20, true, 90), Person("Bob", 30, false, 70), Person("Carol", 40, true, 95)]
step1 = people map Labeled(if row.active then row.name else "inactive", row.score - row.age, row.active and row.score > 80)
step2 = step1 where row.label == "Alice" or row.ok
step3 = step2 map Final(row.label, row.value + 1, if row.ok then "ready" else "hold", not row.ok)
step4 = step3 where row.status == "ready" and row.ok == false
show step4
'''
    p = parse(src)
    validate(p)
    text = lower_execution_ir_to_mlir(p.ast)
    i1 = text.index('@slang_record_mixed_map_to_schema_expr')
    i2 = text.index('@slang_record_mixed_filter_expr', i1)
    i3 = text.index('@slang_record_mixed_map_to_schema_expr', i2)
    i4 = text.index('@slang_record_mixed_filter_expr', i3)
    assert i1 < i2 < i3 < i4
    assert '@slang_record_mixed_map_to_schema_expr' in text
    assert '@slang_record_mixed_filter_expr' in text
