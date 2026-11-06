from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.mlir_backend import lower_execution_ir_to_mlir


def _source():
    return '''
record Person:
    name: Text
    age: Number
    active: Boolean
record Scored:
    label: Text
    value: Number
    ok: Boolean
let people = [Person("A", 20, true), Person("B", 30, false), Person("C", 40, true)]
scored = people map Scored(row.name, row.age * 2, row.active)
normalized = scored map Scored(row.label, row.value + 1, row.ok)
selected = normalized where row.ok and row.value >= 40
ordered = selected sort by row.value desc
total = selected sum row.value
again = selected map Scored(row.label, row.value + 1, row.ok)
show ordered
show total
show again
'''


def test_branching_record_graph_keeps_shared_materialized_handle():
    module = parse(_source())
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)
    selected = pipeline.selected_execution_plan
    assert selected.record_plan is not None
    text = lower_execution_ir_to_mlir(module.ast, pipeline=pipeline)
    # The shared `selected` node is emitted once and its three consumers reuse
    # the same handle; no consumer-specific duplicate materialization is added.
    assert text.count('// S-Lang node: node = "selected#1"') == 1
    assert text.count('selected Record materialization boundary: selected') <= 1
    assert 'slang_sort' in text or 'slang_collection_f64_sort' in text
    assert 'slang_aggregate' in text or 'slang_collection_f64_aggregate' in text


def test_selected_record_boundaries_survive_branching_graph():
    module = parse(_source())
    validate(module)
    pipeline = compile_semantic_pipeline(module.ast)
    rp = pipeline.selected_execution_plan.record_plan
    assert rp is not None
    # A shared downstream node must never appear as two independent materialization
    # boundaries in the selected plan.
    assert len(rp.materialization_boundaries) == len(set(rp.materialization_boundaries))
    assert all(isinstance(x, str) and x for x in rp.materialization_boundaries)
