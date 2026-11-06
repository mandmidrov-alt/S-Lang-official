"""Unified execution contract for S-Lang 0.99.

The contract is the backend-neutral boundary between execution planning and
backend lowering.  It records what the selected plan requires; it does not
select a different strategy and it does not execute code.
"""
from __future__ import annotations
from dataclasses import dataclass

from .compiler_pipeline import CompilerPipeline


@dataclass(frozen=True)
class ExecutionContract:
    operations: tuple[str, ...]
    strategies: tuple[str, ...]
    memory_models: tuple[str, ...]
    effects: tuple[str, ...]
    ordering: str
    parallelism: str
    materialization: str
    requirements: tuple[str, ...]

    @property
    def operation_count(self) -> int:
        return len(self.operations)

    @property
    def strategy_count(self) -> int:
        return len(self.strategies)


def _operations(pipeline: CompilerPipeline) -> tuple[str, ...]:
    mapping = {
        "filter": "filter", "map": "map", "sort": "sort",
        "aggregate": "aggregate", "reduce": "reduce",
        "sequence": "sequence", "goal:select": "choose",
        "goal:path": "find_path", "goal:satisfy": "satisfy", "goal:transition": "sequence",
        "physics.gravity": "physics.gravity", "effect:show": "show",
    }
    return tuple(sorted({mapping[n.kind] for n in pipeline.optimized_ir.nodes if n.kind in mapping}))


def _effects(pipeline: CompilerPipeline) -> tuple[str, ...]:
    effects = set()
    for node in pipeline.optimized_ir.nodes:
        if node.kind == "effect:show":
            effects.add("io")
        else:
            effects.add("pure")
    return tuple(sorted(effects))


def _memory_models(pipeline: CompilerPipeline) -> tuple[str, ...]:
    models = set()
    for choice in pipeline.strategies:
        if choice.strategy in {"scan-filter", "sequential-map", "parallel-filter", "parallel-map"}:
            models.add("linear-buffer")
        elif choice.strategy in {"sequential-aggregate", "sequential-reduce", "fused-filter-map-reduce", "fused-filter-map-aggregate"}:
            models.add("scalar-accumulator")
        elif choice.strategy == "sequence-engine":
            models.add("linear-buffer")
        else:
            models.add("abstract")
    return tuple(sorted(models)) or ("abstract",)


def _parallelism(pipeline: CompilerPipeline) -> str:
    # A parallel capability is a contract requirement only when a selected
    # strategy explicitly requires parallel execution. Merely having
    # scheduler-level independent groups does not force every backend to
    # execute them in parallel; a sequential backend may legally preserve the
    # same semantics.
    if any(choice.strategy.startswith("parallel-") for choice in pipeline.strategies):
        return "parallel-where-independent"
    return "sequential"


def _ordering(pipeline: CompilerPipeline) -> str:
    if _parallelism(pipeline) == "parallel-where-independent":
        return "dependency-ordered"
    return "source-order"


def _materialization(pipeline: CompilerPipeline) -> str:
    groups = pipeline.execution_plan.fusion_groups
    if groups and all(not g.materializes for g in groups):
        return "streaming-when-fused"
    return "backend-defined"


def build_execution_contract(pipeline: CompilerPipeline) -> ExecutionContract:
    """Create a deterministic contract from an already selected plan."""
    strategies = tuple(choice.strategy for choice in pipeline.strategies)
    requirements_set = {f"strategy:{strategy}" for strategy in strategies}
    requirements_set.update(f"memory:{model}" for model in _memory_models(pipeline))
    requirements_set.update(f"effect:{effect}" for effect in _effects(pipeline))
    requirements = tuple(sorted(requirements_set))
    return ExecutionContract(
        operations=_operations(pipeline),
        strategies=strategies,
        memory_models=_memory_models(pipeline),
        effects=_effects(pipeline),
        ordering=_ordering(pipeline),
        parallelism=_parallelism(pipeline),
        materialization=_materialization(pipeline),
        requirements=requirements,
    )


def format_execution_contract(contract: ExecutionContract) -> str:
    lines = ["execution.contract {"]
    lines.append("  operations = " + (", ".join(contract.operations) or "none"))
    lines.append("  strategies = " + (", ".join(contract.strategies) or "none"))
    lines.append("  memory_models = " + ", ".join(contract.memory_models))
    lines.append("  effects = " + ", ".join(contract.effects))
    lines.append("  ordering = " + contract.ordering)
    lines.append("  parallelism = " + contract.parallelism)
    lines.append("  materialization = " + contract.materialization)
    lines.append("  requirements = " + (", ".join(contract.requirements) or "none"))
    lines.append("}")
    return "\n".join(lines)
