"""Canonical pipeline composition IR for S-Lang backends.

This layer turns the operation buckets in the AST into an ordered producer
chain.  Backends can consume the chain without re-implementing the fragile
"find the previous filter/map" logic for every specialized source.
"""
from __future__ import annotations
from dataclasses import dataclass
from .execution_ir import ExecutionIR


@dataclass(frozen=True)
class PipelineStage:
    binding: str
    result: str
    kind: str
    source: str | None
    dependencies: tuple[str, ...]
    input_type: str | None = None
    output_type: str | None = None


@dataclass(frozen=True)
class PipelineIR:
    source: str
    terminal: str
    stages: tuple[PipelineStage, ...]

    @property
    def kinds(self) -> tuple[str, ...]:
        return tuple(stage.kind for stage in self.stages)

    @property
    def fused(self) -> bool:
        return len(self.stages) > 1


def build_pipeline_ir(ir: ExecutionIR, terminal: str) -> PipelineIR:
    """Build one canonical producer chain ending at ``terminal``.

    The function follows ExecutionIR dependencies by result names rather than
    AST bucket order.  It therefore handles ``where -> map -> aggregate`` even
    when the parser stores those operations in separate lists.
    """
    by_binding = ir.by_binding()
    by_result: dict[str, object] = {}
    for node in ir.nodes:
        if node.result is not None:
            by_result[node.result] = node

    node = by_result.get(terminal)
    if node is None:
        raise ValueError(f"pipeline terminal '{terminal}' is not present in ExecutionIR")

    stages: list[PipelineStage] = []
    seen: set[str] = set()
    source = node.binding
    current = node
    while current is not None:
        if current.binding in seen:
            raise ValueError("pipeline IR contains a cycle")
        seen.add(current.binding)
        stages.append(PipelineStage(
            binding=current.binding,
            result=current.result or current.binding,
            kind=current.kind,
            source=_source_from_dependencies(current, by_binding, by_result),
            dependencies=current.dependencies,
            input_type=current.input_type,
            output_type=current.output_type,
        ))
        upstream = _upstream_node(current, by_binding, by_result)
        if upstream is None:
            source = _source_from_dependencies(current, by_binding, by_result) or current.result or current.binding
            break
        current = upstream

    stages.reverse()
    if not stages:
        raise ValueError("empty pipeline")
    root = stages[0].source
    if root is None:
        root = stages[0].result
    return PipelineIR(root, terminal, tuple(stages))


# Alias used only for readable local annotations; the concrete type is the
# ExecutionIR ExecutionNode and importing it here would make the public API
# noisier than necessary.
ExecutionStage = object


def _upstream_node(node, by_binding, by_result=None):
    # External source references carry collection edges for calls such as
    # group_count(selected, ...). Resolve both binding IDs and public result
    # names so canonical pipelines retain transforms before a group terminal.
    by_result = by_result or {}
    references = tuple(dict.fromkeys((*node.dependencies, *node.external_sources)))
    candidates = []
    for reference in references:
        candidate = by_binding.get(reference) or by_result.get(reference)
        if candidate is not None and candidate not in candidates:
            candidates.append(candidate)
    # A collection node normally has exactly one collection producer. Ignore
    # state/function dependencies, which are not collection stages.
    collection = [n for n in candidates if n.kind in {
        "filter", "sort", "map", "group", "aggregate", "reduce", "conditional-pipeline"
    } and n.result is not None]
    return collection[0] if len(collection) == 1 else (collection[-1] if collection else None)


def _source_from_dependencies(node, by_binding, by_result):
    upstream = _upstream_node(node, by_binding, by_result)
    if upstream is not None:
        return upstream.result
    # External/literal sources are represented as unresolved dependencies or
    # simply as the operation's input type. The binding result itself remains
    # the stable fallback for a source-less terminal.
    for dep in node.dependencies:
        if dep in by_binding:
            candidate = by_binding[dep]
            if candidate.result is not None:
                return candidate.result
            if candidate.kind == "binding" and not dep.startswith("@"):
                return dep.rsplit("#", 1)[0]
        elif not dep.startswith("@"):
            return dep
    return None
