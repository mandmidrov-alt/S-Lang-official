"""Deterministic scheduler for S-Lang ExecutionIR.

The scheduler exposes dependency-safe ready sets. It does not execute nodes in
parallel yet; the batches are a semantic opportunity that a future backend may
map to threads, tasks, SIMD or distributed execution when legality permits.
"""
from __future__ import annotations
from dataclasses import dataclass
from .execution_ir import ExecutionIR
from .dependency_graph import build_dependency_graph
from .conflict_graph import group_is_conflict_free

@dataclass(frozen=True)
class ExecutionSchedule:
    batches: tuple[tuple[str, ...], ...]
    parallel_safe_batches: tuple[bool, ...] = ()

    @property
    def order(self) -> tuple[str, ...]:
        return tuple(x for batch in self.batches for x in batch)

    @property
    def independent_batches(self) -> int:
        return sum(1 for b in self.batches if len(b) > 1)

    @property
    def reorderable_batches(self) -> int:
        return sum(1 for ok in self.parallel_safe_batches if ok)


def _dependency_edges(ir):
    return {(edge.before, edge.after) for edge in build_dependency_graph(ir).edges}

def build_schedule(ir: ExecutionIR) -> ExecutionSchedule:
    remaining = {n.binding: set() for n in ir.nodes}
    for before, after in _dependency_edges(ir):
        remaining[after].add(before)
    by_binding = ir.by_binding()
    batches = []
    safe = []
    while remaining:
        ready = tuple(sorted(k for k, deps in remaining.items() if not deps))
        if not ready:
            raise ValueError("execution IR contains a dependency cycle")
        batches.append(ready)
        safe.append(all(by_binding[k].parallel_safe for k in ready) and group_is_conflict_free(ir, ready))
        for k in ready:
            del remaining[k]
        for deps in remaining.values():
            deps.difference_update(ready)
    return ExecutionSchedule(tuple(batches), tuple(safe))

def format_schedule(schedule: ExecutionSchedule) -> str:
    lines = ["execution.schedule {"]
    for i, batch in enumerate(schedule.batches):
        lines.append(f"  batch {i}: " + ", ".join(batch))
    lines.append(f"  batches = {len(schedule.batches)}")
    lines.append(f"  independent_batches = {schedule.independent_batches}")
    lines.append(f"  reorderable_batches = {schedule.reorderable_batches}")
    for i, safe in enumerate(schedule.parallel_safe_batches):
        lines.append(f"  batch {i} parallel_safe = {'yes' if safe else 'no'}")
    lines.append("  parallel_execution = not-yet-implemented")
    lines.append("}")
    return "\n".join(lines)
