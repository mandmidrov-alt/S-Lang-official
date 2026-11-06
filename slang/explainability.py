"""Deterministic explanations for S-Lang execution-strategy decisions."""
from __future__ import annotations
from dataclasses import dataclass
from .compiler_pipeline import CompilerPipeline
from .strategy_selection import algorithm_candidates


@dataclass(frozen=True)
class StrategyExplanation:
    node: str
    selected: str
    profile: str
    selected_score: float | None
    reason: str
    alternatives: tuple[tuple[str, float], ...]
    rejected: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ExecutionExplanation:
    steps: tuple[StrategyExplanation, ...]
    backend: str | None
    execution_profile: object
    deterministic: bool = True


def explain_compiler_pipeline(result: CompilerPipeline) -> ExecutionExplanation:
    rejected_by_node = {c.node: c.rejections for c in result.strategies}
    explanations = []
    for choice in result.strategies:
        selected_score = next((s for name, s in choice.scores if name == choice.strategy), None)
        explanations.append(
            StrategyExplanation(
                node=choice.node,
                selected=choice.strategy,
                profile=choice.profile,
                selected_score=selected_score,
                reason=choice.reason,
                alternatives=choice.scores,
                rejected=rejected_by_node.get(choice.node, ()),
            )
        )
    return ExecutionExplanation(
        steps=tuple(explanations),
        backend=result.selected_execution_plan.backend,
        execution_profile=result.execution_profile,
        deterministic=True,
    )


def format_execution_explanation(explanation: ExecutionExplanation) -> str:
    p = explanation.execution_profile
    lines = ["execution.explain {"]
    lines.append(f"  backend = {explanation.backend or 'unspecified'}")
    lines.append(
        f"  profile = cpu:{p.cpu_cores} parallel:{'yes' if p.allow_parallelism else 'no'}"
    )
    lines.append("  parallelism_policy = " + ("eligible-above-one-core" if p.allow_parallelism and p.cpu_cores > 1 else "disabled-by-profile"))
    for step in explanation.steps:
        score = "none" if step.selected_score is None else f"{step.selected_score:g}"
        lines.append(f"  node {step.node}:")
        lines.append(f"    selected = {step.selected}")
        lines.append(f"    profile = {step.profile}")
        lines.append(f"    selected_score = {score}")
        lines.append(f"    why = {step.reason}")
        if step.alternatives:
            lines.append("    considered = " + ", ".join(f"{n}:{s:g}" for n, s in step.alternatives))
        else:
            lines.append("    considered = none")
        if step.rejected:
            lines.append("    rejected = " + ", ".join(f"{n} ({r})" for n, r in step.rejected))
        else:
            lines.append("    rejected = none")
    lines.append("  model = deterministic-static-explanation")
    lines.append("  runtime_measurements = not-used")
    lines.append("  deterministic = yes")
    lines.append("}")
    return "\n".join(lines)
