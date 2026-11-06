from slang.core import parse, validate
from slang.mlir_backend import lower_execution_ir_to_mlir


def test_mlir_mixed_record_chain_is_emitted_topologically():
    src = '''
record Person:
    name: Text
    age: Number
    active: Boolean
    score: Number

record Summary:
    label: Text
    value: Number

record Final:
    label: Text
    value: Number
    ok: Boolean

let people = [Person("Alice", 20, true, 90), Person("Bob", 30, false, 70), Person("Carol", 40, true, 95)]
summaries = people map Summary(row.name, row.score - row.age)
filtered = summaries where row.value > 50
final = filtered map Final(row.label, row.value + 1, row.value > 60)
show final
'''
    p = parse(src)
    validate(p)
    text = lower_execution_ir_to_mlir(p.ast)
    i_map1 = text.index('%v1 = func.call @slang_record_mixed_map_to_schema_expr')
    i_filter = text.index('%v2 = func.call @slang_record_mixed_filter_expr')
    i_map2 = text.index('%v3 = func.call @slang_record_mixed_map_to_schema_expr')
    assert i_map1 < i_filter < i_map2
    assert '%v1 = func.call @slang_record_mixed_map_to_schema_expr' in text
    assert '%v2 = func.call @slang_record_mixed_filter_expr(%v1' in text
    assert '%v3 = func.call @slang_record_mixed_map_to_schema_expr(%v2' in text
    assert 'nodes = "people#1,summaries#1,filtered#1,final#1,@show:1#1"' in text
