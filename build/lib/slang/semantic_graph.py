"""Unified semantic execution graph for S-Lang.

The graph represents declarative collection operations and goals with one
common dependency model. It is deliberately semantic: nodes describe what
must be computed, while execution backends may later choose how to compute it.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SemanticNode:
    result: str
    kind: str
    source: str | None
    dependencies: tuple[str, ...]
    external_sources: tuple[str, ...]
    strategy: str
    version: int = 1

    @property
    def binding(self) -> str:
        return f"{self.result}#{self.version}"


@dataclass(frozen=True)
class SemanticExecutionGraph:
    nodes: tuple[SemanticNode, ...]

    def by_result(self) -> dict[str, SemanticNode]:
        # Backward-compatible view: repeated bindings resolve to the latest version.
        return {n.result: n for n in self.nodes}

    def by_binding(self) -> dict[str, SemanticNode]:
        return {n.binding: n for n in self.nodes}

    def topological_order(self) -> tuple[str, ...]:
        remaining = {n.binding: set(n.dependencies) for n in self.nodes}
        order: list[str] = []
        while remaining:
            ready = sorted(name for name, deps in remaining.items() if not deps)
            if not ready:
                cycle = ", ".join(sorted(remaining))
                raise ValueError(f"semantic execution graph contains a cycle: {cycle}")
            for name in ready:
                order.append(name)
                del remaining[name]
            for deps in remaining.values():
                deps.difference_update(ready)
        return tuple(order)


def _expr_names(expr: Any) -> set[str]:
    """Use the same conservative expression-name walker as the goal planner."""
    from .goal_plan import _names
    return set(_names(expr))


def _all_ops(module):
    for op in module.sequences:
        if op.target is not None:
            continue  # goal-directed sequences are represented by GoalIR transition nodes
        refs = _expr_names(op.initial) | _expr_names(op.expr)
        if op.target is not None:
            refs |= _expr_names(op.target)
            for candidate in op.candidates:
                refs |= _expr_names(candidate)
        yield ("sequence", op.result, None, refs)
    for op in module.filters:
        yield ("filter", op.result, op.source, _expr_names(op.predicate.expr))
    for op in module.sorts:
        yield ("sort", op.result, op.source, _expr_names(op.spec.expr))
    for op in module.maps:
        yield ("map", op.result, op.source, _expr_names(op.expr))
    for op in module.aggregates:
        yield ("aggregate", op.result, op.source, _expr_names(op.expr))
    for op in module.reduces:
        yield ("reduce", op.result, op.source, _expr_names(op.expr) | _expr_names(op.initial))
    for op in getattr(module, "conditional_pipelines", []):
        refs=_expr_names(op.condition)
        for kind, expr in tuple(op.then_stages) + tuple(op.else_stages):
            if kind == "sort": refs |= _expr_names(expr.expr)
            elif kind == "aggregate": refs |= _expr_names(expr[1])
            elif kind == "reduce": refs |= _expr_names(expr[0]) | _expr_names(expr[1])
            else: refs |= _expr_names(expr)
        yield ("conditional_pipeline", op.result, op.source, refs)


def _goal_nodes(module):
    from .goal_ir import lower_goals
    from .goal_plan import analyze_goals
    plans = analyze_goals(module)
    for plan in plans:
        g = plan.goal
        yield (('goal:transition' if g.kind == 'transition' else g.kind), g.result, g.source, set(plan.dependencies) | set(plan.external_sources), plan.selected_strategy)


def build_semantic_graph(module) -> SemanticExecutionGraph:
    """Build one dependency graph with SSA-like versioned bindings."""
    raw = []
    for kind, result, source, refs in _all_ops(module):
        raw.append((kind, result, source, refs, "reference-execution"))
    # Restore original interleaving across kind-specific AST lists. Use
    # occurrence queues because several operations can share the same
    # (kind, result, source) tuple when a variable is reassigned in place.
    from .ast import source_span_of
    ast_groups = {
        "filter": module.filters, "sort": module.sorts, "map": module.maps,
        "aggregate": module.aggregates, "reduce": module.reduces,
        "conditional_pipeline": getattr(module, "conditional_pipelines", ()),
        "sequence": module.sequences,
    }
    positions = {}
    for kind, group in ast_groups.items():
        for node in group:
            key = (kind, getattr(node, "result", None), getattr(node, "source", None))
            span = source_span_of(node)
            pos = (span.start.line, span.start.column) if span else (10**9, 10**9)
            positions.setdefault(key, []).append(pos)
    for queue in positions.values():
        queue.sort()
    def order_key(item):
        kind, result, source, _refs, _strategy = item
        queue = positions.get((kind, result, source), [])
        return queue.pop(0) if queue else (10**9, 10**9)
    raw.sort(key=order_key)
    raw.extend(_goal_nodes(module))

    # Source order is authoritative for rebinding pipelines. The earlier
    # heuristic that moved self-source operations behind any non-self producer
    # could reorder `map`/`sort`/`where` stages and create incorrect versions.

    versions: dict[str, int] = {}
    produced: dict[str, list[str]] = {}
    nodes = []
    all_bindings: set[str] = set()

    # Assign stable bindings first. This lets the graph resolve a legitimate
    # forward reference such as `filtered = scores where ...` when `scores`
    # is declared later in the source. A prior binding still wins, preserving
    # SSA-like source-order semantics for repeated names.
    planned_bindings: dict[str, list[str]] = {}
    for _kind, result, _source, _refs, _strategy in raw:
        version = len(planned_bindings.get(result, [])) + 1
        planned_bindings.setdefault(result, []).append(f"{result}#{version}")

    planned_binding_set = {binding for bindings in planned_bindings.values() for binding in bindings}

    for kind, result, source, refs, strategy in raw:
        refs = set(refs)
        if source:
            refs.add(source)

        resolved_refs = set()
        for ref in refs:
            prior = produced.get(ref)
            if prior:
                resolved_refs.add(prior[-1])
            elif ref in planned_bindings and len(planned_bindings[ref]) == 1:
                resolved_refs.add(planned_bindings[ref][0])
            else:
                resolved_refs.add(ref)

        version = versions.get(result, 0) + 1
        versions[result] = version
        binding = f"{result}#{version}"
        deps = tuple(sorted(r for r in resolved_refs if r in planned_binding_set and r != binding))
        external = tuple(sorted(r for r in resolved_refs if r not in deps and r not in {"row", "item", "acc", "value", "self"}))
        nodes.append(SemanticNode(result, kind, source, deps, external, strategy, version))
        produced.setdefault(result, []).append(binding)
        all_bindings.add(binding)

    return SemanticExecutionGraph(tuple(nodes))


def format_semantic_graph(graph: SemanticExecutionGraph) -> str:
    lines = ["semantic.graph {"]
    if not graph.nodes:
        lines.append("  // no semantic operations")
    for n in graph.nodes:
        lines.append(f'  node "{n.binding}" logical={n.result} kind={n.kind}')
        lines.append("    dependencies = " + (", ".join(n.dependencies) if n.dependencies else "none"))
        lines.append("    external_sources = " + (", ".join(n.external_sources) if n.external_sources else "none"))
        lines.append("    strategy = " + n.strategy)
    lines.append("  execution_order = " + (" -> ".join(graph.topological_order()) if graph.nodes else "none"))
    lines.append("}")
    return "\n".join(lines)
