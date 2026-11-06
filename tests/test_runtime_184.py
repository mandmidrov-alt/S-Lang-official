from slang.core import parse, validate
from slang.runtime import execute


def run_source(source):
    p = parse(source)
    validate(p)
    return p, execute(p)


def test_conditional_pipeline_true_uses_selected_plan():
    p, (_, trace) = run_source('''
data values:\n    a value 4\n    b value 5\n    c value 6\nlet enabled = true\nresult = values |> if enabled then map value * 10 else map value * 2\n''')
    assert trace.executor == "plan-runtime-conditional"
    assert any(step.strategy == "conditional-pipeline" for step in trace.steps)
    assert p._collections["result"] == [40, 50, 60]


def test_conditional_pipeline_false_uses_selected_plan():
    p, (_, trace) = run_source('''
data values:\n    a value 4\n    b value 5\n    c value 6\nlet enabled = false\nresult = values |> if enabled then map value * 10 else map value * 2\n''')
    assert trace.executor == "plan-runtime-conditional"
    assert any(step.strategy == "conditional-pipeline" for step in trace.steps)
    assert p._collections["result"] == [8, 10, 12]


def test_conditional_pipeline_chain_uses_selected_plan():
    p, (_, trace) = run_source('''
data values:\n    a value 1\n    b value 2\n    c value 3\n    d value 4\nlet enabled = true\nresult = values |> if enabled then (where value >= 2 |> map value * 10 |> sum item) else (where value >= 3 |> reduce 0 with acc + value)\n''')
    assert trace.executor == "plan-runtime-conditional"
    assert any(step.strategy == "conditional-pipeline" for step in trace.steps)
    assert p._collections["result"] == 90
