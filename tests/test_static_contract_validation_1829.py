import pytest

from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.segment_bridge import validate_segment_contracts


def _pipeline():
    module = parse('''
function keep(x: Number) -> Boolean:
    return x > 1

data people:
    a age 1
    b age 2
    c age 3
older = people where keep(age)
mapped = older map age * 2
''')
    validate(module)
    return compile_semantic_pipeline(
        module.ast,
        backend_supported_strategies=("generic", "sequential-map"),
    )


def test_contracts_are_complete_against_ir():
    pipeline = _pipeline()
    contracts = {s.index: s.data_contract for s in pipeline.selected_execution_plan.segments}
    assert validate_segment_contracts(
        pipeline.selected_execution_plan.segments,
        contracts,
        pipeline.dependency_graph.edges,
        ir=pipeline.optimized_ir,
    )


def test_validator_rejects_unnecessary_input():
    pipeline = _pipeline()
    segments = list(pipeline.selected_execution_plan.segments)
    target = segments[1]
    c = target.data_contract
    from dataclasses import replace
    bad = replace(c, inputs=tuple(sorted(set(c.inputs) | {"unrelated"})))
    contracts = {s.index: s.data_contract for s in segments}
    contracts[target.index] = bad
    with pytest.raises(ValueError, match="unnecessary inputs"):
        validate_segment_contracts(segments, contracts, pipeline.dependency_graph.edges, ir=pipeline.optimized_ir)


def test_validator_rejects_missing_output():
    pipeline = _pipeline()
    segments = list(pipeline.selected_execution_plan.segments)
    target = segments[-1]
    c = target.data_contract
    from dataclasses import replace
    bad = replace(c, outputs=())
    contracts = {s.index: s.data_contract for s in segments}
    contracts[target.index] = bad
    with pytest.raises(ValueError, match="contract incomplete for outputs"):
        validate_segment_contracts(segments, contracts, pipeline.dependency_graph.edges, ir=pipeline.optimized_ir)
