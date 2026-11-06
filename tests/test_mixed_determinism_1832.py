from copy import deepcopy

from slang.core import parse, validate
from slang.runtime import execute
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.determinism import observable_snapshot, validate_segment_determinism


SOURCE = '''
function keep(x: Number) -> Boolean:
    return x > 1

data people:
    a age 1
    b age 2
    c age 3
older = people where keep(age)
mapped = older map age * 2
'''


def _module():
    module = parse(SOURCE)
    validate(module)
    return module


def test_mixed_and_unified_execution_have_identical_observable_state():
    unified = _module()
    mixed = _module()
    execute(unified)
    execute(mixed, backend_supported_strategies=("generic", "sequential-map"))
    assert observable_snapshot(unified) == observable_snapshot(mixed)


def test_compiler_rejects_unordered_nondeterministic_segment_plan():
    pipeline = compile_semantic_pipeline(_module().ast)
    assert validate_segment_determinism(pipeline.selected_execution_plan, ir=pipeline.optimized_ir)


def test_repeated_mixed_execution_is_stable():
    first = _module()
    second = deepcopy(first)
    execute(first, backend_supported_strategies=("generic", "sequential-map"))
    execute(second, backend_supported_strategies=("generic", "sequential-map"))
    assert observable_snapshot(first) == observable_snapshot(second)
