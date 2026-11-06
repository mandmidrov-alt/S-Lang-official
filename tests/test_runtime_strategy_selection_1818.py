from slang.compiler_pipeline import compile_semantic_pipeline
from slang import core
from slang.runtime_capability import runtime_strategy_supported


def compile_source(text):
    module = core.parse(text)
    core.validate(module)
    return module, compile_semantic_pipeline(module.ast)


def test_strategy_selection_prefers_runtime_supported_specialization():
    _, pipeline = compile_source('''
let values = [1, 2, 3]
result = values map item + 1
show result
''')
    choice = next(s for s in pipeline.strategies if s.node.startswith('result#'))
    assert choice.strategy == 'sequential-map'
    assert choice.runtime_supported
    assert 'runtime contract available' in choice.reason
    assert ('generic', "strategy 'generic' is semantically legal but has no unified runtime contract") in choice.rejections


def test_runtime_unsupported_semantic_candidate_is_rejected_when_supported_one_exists():
    _, pipeline = compile_source('''
let values = [1, 2, 3]
result = values map item + 1
show result
''')
    choice = next(s for s in pipeline.strategies if s.node.startswith('result#'))
    assert ('generic', "strategy 'generic' is semantically legal but has no unified runtime contract") in choice.rejections


def test_runtime_support_matrix_is_explicit():
    assert runtime_strategy_supported('map', 'sequential-map')
    assert runtime_strategy_supported('goal:path', 'graph-shortest-path')
    assert runtime_strategy_supported('physics.gravity', 'physics-domain')
    assert runtime_strategy_supported('binding', 'generic')
    assert not runtime_strategy_supported('map', 'generic')
    assert not runtime_strategy_supported('goal:path', 'generic')
