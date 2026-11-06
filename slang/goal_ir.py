"""Unified semantic IR for goal-oriented S-Lang operations.

The goal IR deliberately describes *what result is required* and its
constraints/objective. It does not encode the search algorithm used by a
runtime or backend.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GoalIR:
    """One normalized goal operation.

    kind is one of ``select``, ``path`` or ``satisfy``. Fields that do not
    apply to a kind remain None/empty. This keeps the compiler's goal model
    uniform while preserving the source-level domain distinctions.
    """
    result: str
    kind: str
    source: str | None = None
    constraints: tuple[Any, ...] = ()
    objective: str | None = None
    key: Any = None
    direction: str | None = None
    start: str | None = None
    end: str | None = None
    variables: tuple[tuple[str, int, int], ...] = ()
    target: Any = None
    candidates: tuple[Any, ...] = ()
    transition_constraints: tuple[Any, ...] = ()


def lower_goals(module) -> list[GoalIR]:
    """Normalize all goal AST nodes into one deterministic ordered list."""
    out: list[GoalIR] = []
    for op in module.sequences:
        if op.target is not None:
            out.append(GoalIR(
                result=op.result,
                kind="transition",
                source=None,
                constraints=tuple(op.constraints or ((op.constraint,) if op.constraint is not None else ())),
                objective="distance-to-target",
                target=op.target,
                candidates=op.candidates,
                transition_constraints=tuple(op.constraints or ((op.constraint,) if op.constraint is not None else ())),
            ))
    for op in module.goals:
        constraints = (op.predicate.expr,) if op.predicate is not None else ()
        out.append(GoalIR(
            result=op.result,
            kind="select",
            source=op.source,
            constraints=constraints,
            objective="key",
            key=op.key,
            direction=op.direction,
        ))
    for op in module.path_goals:
        out.append(GoalIR(
            result=op.result,
            kind="path",
            source=op.source,
            constraints=(),
            objective=op.objective,
            start=op.start,
            end=op.end,
        ))
    for op in module.satisfy_goals:
        out.append(GoalIR(
            result=op.result,
            kind="satisfy",
            source=None,
            constraints=op.constraints,
            objective="lexicographic",
            variables=op.variables,
        ))
    return out


def format_goal_ir(goals: list[GoalIR]) -> str:
    """Produce a stable human-readable representation for inspection/tests."""
    lines = ["goal.module {"]
    if not goals:
        lines.append("  // no goals")
    for g in goals:
        lines.append(f'  goal "{g.result}" kind={g.kind}')
        if g.source is not None:
            lines.append(f'    source = {g.source}')
        if g.kind == "select":
            if g.constraints:
                lines.append(f"    constraint = {g.constraints[0]!r}")
            lines.append(f"    objective = {g.direction} key={g.key!r}")
        elif g.kind == "path":
            lines.append(f"    from = {g.start}")
            lines.append(f"    to = {g.end}")
            lines.append(f"    objective = minimizing {g.objective}")
        elif g.kind == "transition":
            lines.append(f"    objective = minimize {g.objective}")
            lines.append(f"    target = {g.target!r}")
            lines.append("    candidates = " + str(len(g.candidates)))
            for c in g.transition_constraints:
                lines.append(f"    constraint = {c!r}")
        elif g.kind == "satisfy":
            for name, lo, hi in g.variables:
                lines.append(f"    domain = {name} in {lo}..{hi}")
            for c in g.constraints:
                lines.append(f"    constraint = {c!r}")
            lines.append(f"    selection = {g.objective}")
    lines.append("}")
    return "\n".join(lines)
