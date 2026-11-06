"""Semantics-preserving optimization of S-Lang ExecutionIR (0.73).

This pass deliberately optimizes the execution graph rather than source syntax.
It currently performs two conservative transformations:

* transitive dependency reduction: remove an edge A -> C when A -> B -> C
  already exists;
* dead pure-definition elimination: remove pure definition nodes that have no
  consumers. Effectful nodes and concrete program results are never removed.

No runtime measurements or speculative transformations are used.
"""
from __future__ import annotations
from dataclasses import dataclass
from .execution_ir import ExecutionIR, ExecutionNode


@dataclass(frozen=True)
class ExecutionOptimizationReport:
    transitive_dependencies_removed: int = 0
    dead_definitions_removed: int = 0
    nodes_specialized: int = 0

    @property
    def total(self) -> int:
        return self.transitive_dependencies_removed + self.dead_definitions_removed + self.nodes_specialized


def _transitive_reduction(nodes: list[ExecutionNode]) -> tuple[list[ExecutionNode], int]:
    by = {n.binding: n for n in nodes}
    removed = 0
    out: list[ExecutionNode] = []

    for node in nodes:
        deps = set(node.dependencies)
        # A dependency d is redundant if another direct dependency x can reach d.
        redundant: set[str] = set()
        for d in deps:
            stack = [x for x in deps if x != d]
            seen: set[str] = set()
            while stack:
                cur = stack.pop()
                if cur == d:
                    redundant.add(d)
                    break
                if cur in seen or cur not in by:
                    continue
                seen.add(cur)
                stack.extend(by[cur].dependencies)
        if redundant:
            removed += len(redundant)
            node = ExecutionNode(
                node.binding, node.kind, node.result,
                tuple(sorted(deps - redundant)), node.external_sources,
                node.pure, node.definition, node.deterministic, node.access,
                node.order_sensitive, node.effects, node.memory_reads,
                node.memory_writes, node.memory_regions,
                node.memory_region_specs, node.cardinality,
                node.cardinality_confidence, node.cardinality_reason,
                node.data_shape, node.optimization_hints, node.input_type, node.output_type, node.input_schema, node.output_schema,
            )
        out.append(node)
    return out, removed


def _remove_dead_definitions(nodes: list[ExecutionNode]) -> tuple[list[ExecutionNode], int]:
    consumers: dict[str, int] = {n.binding: 0 for n in nodes}
    for node in nodes:
        for dep in node.dependencies:
            if dep in consumers:
                consumers[dep] += 1

    keep: list[ExecutionNode] = []
    removed = 0
    for node in nodes:
        # Definitions are compile-time semantic declarations. If nothing in
        # the executable graph references one, dropping it has no observable
        # effect. Never remove executable/effectful nodes.
        if node.definition and node.pure and not node.effects and consumers[node.binding] == 0:
            removed += 1
            continue
        keep.append(node)
    return keep, removed


def optimize_execution_ir(ir: ExecutionIR) -> tuple[ExecutionIR, ExecutionOptimizationReport]:
    nodes, transitive = _transitive_reduction(list(ir.nodes))
    nodes, dead = _remove_dead_definitions(nodes)
    final_nodes = []
    specialized_count = 0
    for original in nodes:
        shape = original.data_shape
        hints = list(original.optimization_hints)
        if shape is not None:
            if shape.exact and shape.lower == 0:
                hints.append("empty-result")
            elif shape.exact and shape.lower == 1:
                hints.append("singleton-result")
            elif shape.exact and shape.lower is not None and shape.lower <= 32:
                hints.append("small-cardinality")
            elif shape.lower is not None and shape.lower >= 1024:
                hints.append("large-cardinality")
            if shape.complexity == "nlogn":
                hints.append("nlogn-specialized")
        unique = tuple(dict.fromkeys(hints))
        if unique != original.optimization_hints:
            specialized_count += 1
            original = ExecutionNode(
                original.binding, original.kind, original.result, original.dependencies,
                original.external_sources, original.pure, original.definition,
                original.deterministic, original.access, original.order_sensitive,
                original.effects, original.memory_reads, original.memory_writes,
                original.memory_regions, original.memory_region_specs, original.cardinality,
                original.cardinality_confidence, original.cardinality_reason,
                original.data_shape, unique, original.input_type, original.output_type, original.input_schema, original.output_schema
            )
        final_nodes.append(original)
    return ExecutionIR(tuple(final_nodes)), ExecutionOptimizationReport(transitive, dead, specialized_count)


def format_execution_optimization(report: ExecutionOptimizationReport) -> str:
    return "\n".join([
        "execution.optimization {",
        f"  transitive_dependencies_removed = {report.transitive_dependencies_removed}",
        f"  dead_definitions_removed = {report.dead_definitions_removed}",
        f"  nodes_specialized = {report.nodes_specialized}",
        f"  total_transformations = {report.total}",
        "  model = semantics-preserving-static",
        "  runtime_measurements = not-used",
        "  speculative = no",
        "}",
    ])
