from slang.core import parse
from slang.execution_profile import ExecutionProfile
from slang.runtime import execute
from slang.determinism import observable_snapshot


def _program():
    rows = "".join(f"    a{i} value {i}\n" for i in range(100))
    return parse("data values:\n" + rows + "result = values |> map value * 7\n")



def test_parallel_map_matches_sequential_observable_state():
    sequential, _ = execute(_program(), ExecutionProfile(cpu_cores=1, allow_parallelism=False))
    parallel, trace = execute(_program(), ExecutionProfile(cpu_cores=4, allow_parallelism=True))
    assert any(step.strategy == "parallel-map" for step in trace.steps)
    assert observable_snapshot(parallel) == observable_snapshot(sequential)


def test_parallel_map_is_repeatable():
    profile = ExecutionProfile(cpu_cores=4, allow_parallelism=True)
    snapshots = []
    for _ in range(4):
        module, trace = execute(_program(), profile)
        assert any(step.strategy == "parallel-map" for step in trace.steps)
        snapshots.append(observable_snapshot(module))
    assert snapshots.count(snapshots[0]) == len(snapshots)


def test_parallel_binding_level_matches_sequential_level():
    source = parse('''
let a = 10
let b = 20
let c = a + b
''')
    sequential, _ = execute(source, ExecutionProfile(cpu_cores=1, allow_parallelism=False))
    parallel, trace = execute(parse('''
let a = 10
let b = 20
let c = a + b
'''), ExecutionProfile(cpu_cores=4, allow_parallelism=True))
    assert observable_snapshot(parallel) == observable_snapshot(sequential)
