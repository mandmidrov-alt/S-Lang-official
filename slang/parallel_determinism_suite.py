"""Acceptance checks for deterministic real parallel execution."""
from __future__ import annotations

from .core import parse
from .execution_profile import ExecutionProfile
from .runtime import execute
from .determinism import observable_snapshot


def _program():
    rows = "".join(f"    a{i} value {i}\n" for i in range(100))
    return parse("data values:\n" + rows + "result = values |> map value * 7\n")


def run_suite() -> list[dict[str, object]]:
    sequential, _ = execute(_program(), ExecutionProfile(cpu_cores=1, allow_parallelism=False))
    parallel, trace = execute(_program(), ExecutionProfile(cpu_cores=4, allow_parallelism=True))
    sequential_snapshot = observable_snapshot(sequential)
    parallel_snapshot = observable_snapshot(parallel)
    repeated = []
    profile = ExecutionProfile(cpu_cores=4, allow_parallelism=True)
    for _ in range(3):
        module, repeat_trace = execute(_program(), profile)
        repeated.append((observable_snapshot(module), any(s.strategy == "parallel-map" for s in repeat_trace.steps)))
    return [
        {
            "name": "parallel_matches_sequential",
            "stable": parallel_snapshot == sequential_snapshot and any(s.strategy == "parallel-map" for s in trace.steps),
        },
        {
            "name": "parallel_repeatable",
            "stable": bool(repeated) and all(flag for _, flag in repeated) and all(snap == repeated[0][0] for snap, _ in repeated),
        },
    ]
