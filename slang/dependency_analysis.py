from __future__ import annotations
from dataclasses import dataclass
from .execution_ir import ExecutionIR
from .dependency_graph import DependencyGraph, build_dependency_graph
from .conflict_graph import group_is_conflict_free

@dataclass(frozen=True)
class DependencyAnalysis:
    levels: tuple[tuple[str, ...], ...]
    critical_path: tuple[str, ...]
    critical_path_length: int
    parallel_candidates: tuple[tuple[str, ...], ...]
    parallel_safe_candidates: tuple[tuple[str, ...], ...]


def analyze_dependency_graph(ir: ExecutionIR, graph: DependencyGraph | None = None) -> DependencyAnalysis:
    graph = graph or build_dependency_graph(ir)
    nodes = {n.binding for n in ir.nodes}
    incoming = {n: set() for n in nodes}
    outgoing = {n: set() for n in nodes}
    for edge in graph.edges:
        if edge.before in nodes and edge.after in nodes:
            incoming[edge.after].add(edge.before)
            outgoing[edge.before].add(edge.after)

    remaining = {n: set(v) for n, v in incoming.items()}
    levels: list[tuple[str, ...]] = []
    while remaining:
        ready = tuple(sorted(n for n, deps in remaining.items() if not deps))
        if not ready:
            raise ValueError("dependency graph contains a cycle")
        levels.append(ready)
        for n in ready:
            del remaining[n]
        for deps in remaining.values():
            deps.difference_update(ready)

    # Longest dependency path. Ties are resolved lexicographically so the
    # analysis remains deterministic.
    distance = {n: 1 for n in nodes}
    previous: dict[str, str | None] = {n: None for n in nodes}
    for level in levels:
        for n in level:
            for child in sorted(outgoing[n]):
                candidate = distance[n] + 1
                if candidate > distance[child] or (candidate == distance[child] and (previous[child] is None or n < previous[child])):
                    distance[child] = candidate
                    previous[child] = n
    end = min((n for n in nodes if distance[n] == max(distance.values())), default=None)
    path: list[str] = []
    while end is not None:
        path.append(end)
        end = previous[end]
    path.reverse()

    by = ir.by_binding()
    parallel_safe = tuple(
        batch for batch in levels
        if len(batch) > 1 and all(by[n].parallel_safe for n in batch) and group_is_conflict_free(ir, batch)
    )
    parallel_candidates = tuple(batch for batch in levels if len(batch) > 1)
    return DependencyAnalysis(
        levels=tuple(levels),
        critical_path=tuple(path),
        critical_path_length=len(path),
        parallel_candidates=parallel_candidates,
        parallel_safe_candidates=parallel_safe,
    )


def format_dependency_analysis(analysis: DependencyAnalysis) -> str:
    lines = ["dependency.analysis {"]
    for i, level in enumerate(analysis.levels):
        lines.append(f"  level {i}: " + ", ".join(level))
    lines.append(f"  levels = {len(analysis.levels)}")
    lines.append(f"  critical_path_length = {analysis.critical_path_length}")
    lines.append("  critical_path = " + (" -> ".join(analysis.critical_path) if analysis.critical_path else "none"))
    lines.append(f"  parallel_candidate_groups = {len(analysis.parallel_candidates)}")
    for i, group in enumerate(analysis.parallel_candidates):
        lines.append(f"  parallel_candidates {i}: " + ", ".join(group))
    lines.append(f"  parallel_safe_groups = {len(analysis.parallel_safe_candidates)}")
    for i, group in enumerate(analysis.parallel_safe_candidates):
        lines.append(f"  parallel_safe {i}: " + ", ".join(group))
    lines.append("  execution = analysis-only")
    lines.append("}")
    return "\n".join(lines)
