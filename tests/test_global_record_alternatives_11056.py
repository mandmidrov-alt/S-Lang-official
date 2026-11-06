from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.optimizer import enumerate_record_plan_options


def _source():
    return '''
record Person:
    name: Text
    age: Number

record R1:
    label: Text
    value: Number

record R2:
    label: Text
    value: Number

record R3:
    label: Text
    value: Number

let people = [Person("A", 20), Person("B", 30)]
a = people map R1(row.name, row.age + 1)
b = a map R2(row.label, row.value + 2)
c = b map R3(row.label, row.value + 3)
show c
'''


def test_record_alternatives_are_generated():
    module = parse(_source())
    validate(module)
    options = enumerate_record_plan_options(type('P', (), {'ast': module.ast})())
    assert len(options) >= 2
    assert any(o.mode == 'full' for o in options)
    assert any(o.mode in {'partial', 'materialized'} for o in options)


def test_global_optimizer_includes_record_alternatives():
    module = parse(_source())
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)
    cost = pipeline.global_plan_cost
    assert cost is not None
    assert cost.record_plan_alternatives >= 2
    assert cost.strategy_search_space >= cost.record_plan_alternatives
    assert cost.record_plan_mode in {'full', 'partial', 'materialized'}
