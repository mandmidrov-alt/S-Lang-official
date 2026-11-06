from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from slang import core
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.runtime import execute


def test_function_reference_is_a_plan_dependency():
    source = '''
function double(x: Number) -> Number:
    return x * 2
let transform = double
result = transform(5)
show result
'''
    p = core.parse(source)
    core.validate(p)
    pipeline = compile_semantic_pipeline(p.ast)
    order = [step.node for step in pipeline.selected_execution_plan.steps]
    assert order.index('@fn:double') < order.index('transform#1') < order.index('result#1')
    _, trace = execute(p)
    assert trace.executor == 'plan-runtime-segmented'
    assert p._bindings['result'] == 10


def test_goal_transition_has_direct_specialized_runtime_support():
    source = '''
sequence values from 1 for 4 steps using value + 1
show values
'''
    p = core.parse(source)
    core.validate(p)
    _, trace = execute(p)
    assert trace.executor in {'plan-runtime-goals', 'plan-runtime-segmented'}
    assert p._collections['values'] == [1, 2, 3, 4]


def test_goal_transition_gets_state_transition_strategy():
    source = '''
sequence path from 1 for up to 4 steps toward 5 choosing:
    value + 1
    value + 2

show path
'''
    p = core.parse(source)
    core.validate(p)
    pipeline = compile_semantic_pipeline(p.ast)
    assert any(step.strategy == "state-transition" for step in pipeline.selected_execution_plan.steps)
    _, trace = execute(p)
    assert trace.executor == "plan-runtime-goals"
    assert p._collections["path"] == [1, 3, 5, 6]
