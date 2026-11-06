from slang.core import parse, validate
from slang.mlir_backend import lower_execution_ir_to_mlir

def source():
    return '''
record Person:
    name: Text
    age: Number
    score: Number

record Summary:
    label: Text
    value: Number

let people = [Person("Ada", 36, 90), Person("Bob", 15, 70)]
summaries = people map Summary(row.name, row.score - row.age)
selected = summaries where row.value >= 50
show selected
'''

def test_mlir_uses_output_schema_for_intermediate_record_storage():
    p = parse(source()); validate(p)
    text = lower_execution_ir_to_mlir(p.ast)
    assert 'record-schema-storage summaries_1 output Summary' in text
    assert 'label:Text->%schema_' in text
    assert 'value:Number->%schema_' in text
    assert 'memref.alloca() : memref<1xf64>' in text
    assert 'output_schema_storage = "label->%schema_' in text

def test_mlir_storage_is_schema_driven_not_ast_reinferred():
    p = parse(source()); validate(p)
    text = lower_execution_ir_to_mlir(p.ast)
    summary_section = text[text.index('record-schema-storage summaries_1 output Summary'):]
    assert 'value:Number' in summary_section
    storage_line = next(line for line in summary_section.splitlines() if line.startswith('    // schema-fields summaries_1'))
    assert 'age:Number' not in storage_line
    assert 'score:Number' not in storage_line
