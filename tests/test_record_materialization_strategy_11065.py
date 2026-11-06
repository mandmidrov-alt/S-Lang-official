from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from tests.test_record_field_projection_11063 import _source


def test_record_materialization_strategy_prefers_projection_for_field_consumer():
    module = parse(_source('row.id > 0'))
    validate(module)
    cost = compile_semantic_pipeline(module.ast).global_plan_cost
    assert cost is not None
    assert cost.record_materialization_strategies
    modes = {mode for _, mode, _, _ in cost.record_materialization_strategies}
    assert 'projected' in modes


def test_recompute_candidate_is_restricted_to_record_producing_consumers():
    module = parse(_source('row.id > 0'))
    validate(module)
    cost = compile_semantic_pipeline(module.ast).global_plan_cost
    assert cost is not None
    for endpoint, mode, _, fields in cost.record_materialization_strategies:
        assert fields
        assert mode != 'recompute'
