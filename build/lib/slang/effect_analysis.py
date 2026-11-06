"""Formal, backend-neutral effect analysis for S-Lang 1.5.

Effects are semantic properties, not implementation hints.  They constrain
reordering and parallel execution while leaving pure computations free to be
optimized.
"""
from __future__ import annotations
from dataclasses import dataclass

PURE = "pure"
STATE_READ = "state-read"
STATE_WRITE = "state-write"
IO = "io"
EXTERNAL = "external"

@dataclass(frozen=True)
class EffectSummary:
    node: str
    effects: tuple[str, ...]
    purity: str
    reorderable: bool
    parallel_safe: bool
    order_sensitive: bool
    reason: str

    @property
    def effectful(self) -> bool:
        return bool(self.effects)


def classify_node(node) -> EffectSummary:
    raw = {str(effect).lower() for effect in node.effects}
    if any(dep in {"@fn:read", "@fn:write", "@fn:read_lines", "@fn:write_lines", "@fn:exists"} for dep in node.dependencies):
        raw.add(IO)
    # Existing ExecutionIR uses the broad `state` marker for writes. Keep the
    # distinction explicit at the public effect layer.
    if "state" in raw:
        raw.discard("state")
        raw.add(STATE_WRITE)
    if not raw:
        effects = ()
        purity = PURE
        reason = "no observable state or external effect"
    else:
        effects = tuple(sorted(raw))
        purity = "effectful"
        reason = "observable effect constrains reordering"
    safe = node.reorderable and not ({STATE_WRITE, IO, EXTERNAL} & set(effects))
    return EffectSummary(
        node=node.binding,
        effects=effects,
        purity=purity,
        reorderable=node.reorderable and not ({STATE_WRITE, IO, EXTERNAL} & set(effects)),
        parallel_safe=safe,
        order_sensitive=node.order_sensitive or not safe,
        reason=reason,
    )


def analyze_effects(ir) -> tuple[EffectSummary, ...]:
    return tuple(classify_node(node) for node in ir.nodes)


def validate_strategy_effects(ir, strategies) -> tuple[str, ...]:
    by = {n.binding: classify_node(n) for n in ir.nodes}
    errors = []
    for choice in strategies:
        summary = by.get(choice.node)
        if summary is None:
            continue
        if choice.strategy.startswith("parallel-") and not summary.parallel_safe:
            errors.append(
                f"{choice.node}: strategy {choice.strategy} is incompatible with effects "
                f"{', '.join(summary.effects) or 'none'}"
            )
    return tuple(errors)


def format_effect_analysis(summaries: tuple[EffectSummary, ...]) -> str:
    lines = ["effect.analysis {"]
    for s in summaries:
        lines.append(f"  node {s.node}:")
        lines.append("    effects = " + (", ".join(s.effects) if s.effects else "pure"))
        lines.append("    purity = " + s.purity)
        lines.append("    reorderable = " + ("yes" if s.reorderable else "no"))
        lines.append("    parallel_safe = " + ("yes" if s.parallel_safe else "no"))
        lines.append("    order_sensitive = " + ("yes" if s.order_sensitive else "no"))
        lines.append("    reason = " + s.reason)
    lines.append(f"  nodes = {len(summaries)}")
    lines.append("  model = explicit-effect-aware-semantics")
    lines.append("  deterministic = yes")
    lines.append("}")
    return "\n".join(lines)
