from slang.core import parse, validate
from slang.runtime import execute
from slang.execution_profile import ExecutionProfile


def test_runtime_uses_plan_executor_for_pure_bindings():
    p = parse('''
let a = [1, 2, 3]
let b = [4, 5, 6]
let c = sum_numbers(a)
let d = sum_numbers(b)
''')
    validate(p)
    module, trace = execute(p)
    assert trace.executor == "plan-runtime"
    assert module._bindings["c"] == 6
    assert module._bindings["d"] == 15


def test_runtime_parallel_level_executes_independent_bindings():
    p = parse('''
let a = [1, 2, 3]
let b = [4, 5, 6]
let c = sum_numbers(a)
let d = sum_numbers(b)
''')
    validate(p)
    profile = ExecutionProfile(cpu_cores=4, allow_parallelism=True)
    module, trace = execute(p, execution_profile=profile)
    assert trace.executor == "plan-runtime"
    assert module._bindings["c"] == 6
    assert module._bindings["d"] == 15
    assert any(step.strategy == "parallel-generic" for step in trace.steps)


def test_runtime_falls_back_for_stateful_programs():
    p = parse('''
state total = 0
set total = 1
''')
    validate(p)
    module, trace = execute(p)
    assert trace.executor == "plan-runtime-stateful"
