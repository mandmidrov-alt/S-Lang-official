from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline


def test_global_plan_includes_record_fusion_signal():
    source = '''
record Person:
    name: Text
    age: Number

record Summary:
    label: Text
    value: Number

let people = [Person("A", 20), Person("B", 30)]
summaries = people map Summary(row.name, row.age + 1)
final = summaries map Summary(row.label, row.value + 2)
'''
    module = parse(source)
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)
    cost = pipeline.global_plan_cost
    assert cost is not None
    assert cost.record_fusion_fusions >= 1
    assert cost.record_fusion_cost > 0
