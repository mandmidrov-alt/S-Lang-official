from slang.core import parse, validate
from slang.execution_ir import build_execution_ir

def test_execution_ir_carries_resolved_collection_types_through_record_chain():
    src='''
record Summary:
    name: Text
    value: Number

data people:
    Alice age 20 score 90
    Bob age 30 score 70

adults = people where row.age >= 18
summaries = adults map Summary("x", row.age + 1)
selected = summaries where row.value > 30
show selected
'''
    p=parse(src); validate(p); ir=build_execution_ir(p.ast)
    nodes={n.result:n for n in ir.nodes if n.result}
    assert nodes['adults'].input_type == 'List<Row>'
    assert nodes['adults'].output_type == 'List<Row>'
    assert nodes['summaries'].input_type == 'List<Row>'
    assert nodes['summaries'].output_type == 'List<Record<Summary>>'
    assert nodes['selected'].input_type == 'List<Record<Summary>>'
    assert nodes['selected'].output_type == 'List<Record<Summary>>'
