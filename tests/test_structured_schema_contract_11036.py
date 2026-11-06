from slang.core import parse, validate
from slang.execution_ir import build_execution_ir
from slang.compiler_pipeline import compile_semantic_pipeline
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
adults = people where row.age >= 18
summaries = adults map Summary(row.name, row.score - row.age)
selected = summaries where row.value > 50
'''


def test_execution_ir_carries_structured_record_schema():
    program = parse(source())
    validate(program)
    ir = build_execution_ir(program.ast)
    by = ir.by_binding()
    adults = by['adults#1']
    summaries = by['summaries#1']
    assert adults.input_schema.name == 'Person'
    assert tuple((f.name, f.type_name) for f in adults.input_schema.fields) == (
        ('name', 'Text'), ('age', 'Number'), ('score', 'Number'))
    assert adults.output_schema.name == 'Person'
    assert summaries.input_schema.name == 'Person'
    assert summaries.output_schema.name == 'Summary'
    assert tuple((f.name, f.type_name) for f in summaries.output_schema.fields) == (
        ('label', 'Text'), ('value', 'Number'))


def test_schema_contract_survives_optimized_pipeline():
    program = parse(source())
    validate(program)
    pipeline = compile_semantic_pipeline(program.ast)
    contract = dict((b, (i, o)) for b, i, o in pipeline.optimized_ir.schema_contract())
    assert contract['summaries#1'][0].name == 'Person'
    assert contract['summaries#1'][1].name == 'Summary'
    assert contract['selected#1'][0].name == 'Summary'
    assert contract['selected#1'][1].name == 'Summary'


def test_mlir_emits_structured_schema_without_ast_field_recovery():
    program = parse(source())
    validate(program)
    mlir = lower_execution_ir_to_mlir(program.ast)
    assert 'input_schema = "Person[name:Text,age:Number,score:Number]"' in mlir
    assert 'output_schema = "Summary[label:Text,value:Number]"' in mlir
