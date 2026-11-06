"""Semantic execution planning for S-Lang goals.

The planner converts GoalIR into an explicit, deterministic ExecutionPlan.
A strategy is selected only when its applicability is proven from the goal's
semantics. Runtime implementations may later be replaced by optimized
backends without changing the source language.
"""
from __future__ import annotations
from dataclasses import dataclass
from .ast import Name, Field, Binary, Compare, Logical, Call, Property, Literal, Conditional, Expr
from .goal_ir import GoalIR, lower_goals


@dataclass(frozen=True)
class GoalStrategy:
    name: str
    applicable: bool
    reason: str


@dataclass(frozen=True)
class GoalPlan:
    goal: GoalIR
    dependencies: tuple[str, ...]
    external_sources: tuple[str, ...]
    independent: bool
    strategies: tuple[GoalStrategy, ...]
    selected_strategy: str

    @property
    def strategy_candidates(self) -> tuple[str, ...]:
        return tuple(s.name for s in self.strategies)


@dataclass(frozen=True)
class ExecutionPlan:
    goals: tuple[GoalPlan, ...]

    @property
    def selected(self) -> tuple[str, ...]:
        return tuple(g.selected_strategy for g in self.goals)



def propagate_integer_bounds(variables, constraints):
    """Sound interval narrowing for finite integer satisfy domains.

    Returns a deterministic {name: [lo, hi]} map. Unsupported/non-linear
    constraints are intentionally ignored and remain checked by the final
    evaluator.
    """
    import math
    bounds = {name: [int(lo), int(hi)] for name, lo, hi in variables}

    def linear(expr):
        from .ast import Literal, Name, Binary
        if isinstance(expr, Literal) and isinstance(expr.value, (int, float)) and not isinstance(expr.value, bool):
            return ({}, float(expr.value))
        if isinstance(expr, Name) and expr.name in bounds:
            return ({expr.name: 1.0}, 0.0)
        if isinstance(expr, Binary):
            a, b = linear(expr.left), linear(expr.right)
            if a is None or b is None:
                return None
            ac, ak = a; bc, bk = b
            if expr.op in {"+", "-"}:
                sign = 1.0 if expr.op == "+" else -1.0
                coeff = dict(ac)
                for n, c in bc.items(): coeff[n] = coeff.get(n, 0.0) + sign * c
                return ({n:c for n,c in coeff.items() if c}, ak + sign * bk)
            if expr.op == "*":
                if ac and bc: return None
                if ac: return ({n:c*bk for n,c in ac.items()}, ak*bk)
                if bc: return ({n:c*ak for n,c in bc.items()}, bk*ak)
                return ({}, ak*bk)
            if expr.op == "/" and not bc and bk != 0:
                return ({n:c/bk for n,c in ac.items()}, ak/bk)
        return None

    def interval(coeffs, const):
        lo = hi = const
        for n, c in coeffs.items():
            a, b = bounds[n]
            x, y = (c*a, c*b) if c >= 0 else (c*b, c*a)
            lo += x; hi += y
        return lo, hi

    for _ in range(max(1, len(bounds) * 2)):
        changed = False
        for constraint in constraints:
            if not isinstance(constraint, Compare):
                continue
            left, right = linear(constraint.left), linear(constraint.right)
            if left is None or right is None: continue
            lc, lk = left; rc, rk = right
            coeff = dict(lc)
            for n, c in rc.items(): coeff[n] = coeff.get(n, 0.0) - c
            coeff = {n:c for n,c in coeff.items() if c}
            constant = lk - rk
            for name, c in tuple(coeff.items()):
                other = {n:v for n,v in coeff.items() if n != name}
                omin, omax = interval(other, constant)
                cur_lo, cur_hi = bounds[name]
                if constraint.op == "==":
                    target_lo, target_hi = -omax/c, -omin/c
                elif constraint.op == "<=":
                    target_lo, target_hi = ((-float("inf"), -omin/c) if c > 0 else (-omax/c, float("inf")))
                elif constraint.op == ">=":
                    target_lo, target_hi = ((-omax/c, float("inf")) if c > 0 else (-float("inf"), -omin/c))
                elif constraint.op == "<":
                    # c*x + other + constant < 0. For integer x, strict
                    # inequality is equivalent to <= -1. Projection keeps the
                    # most permissive value of the other variables.
                    target_lo, target_hi = ((-float("inf"), (-omin-1)/c) if c > 0 else ((-omin-1)/c, float("inf")))
                elif constraint.op == ">":
                    # c*x + other + constant > 0. For integer x, strict
                    # inequality is equivalent to >= 1.
                    target_lo, target_hi = (((-omax+1)/c, float("inf")) if c > 0 else (-float("inf"), (-omax+1)/c))
                else:
                    continue
                new_lo = cur_lo if math.isinf(target_lo) and target_lo < 0 else max(cur_lo, math.ceil(target_lo))
                new_hi = cur_hi if math.isinf(target_hi) and target_hi > 0 else min(cur_hi, math.floor(target_hi))
                if new_lo != cur_lo or new_hi != cur_hi:
                    bounds[name] = [new_lo, new_hi]
                    changed = True
        if any(lo > hi for lo, hi in bounds.values()) or not changed:
            break
    return bounds

def _names(expr: Expr | None) -> set[str]:
    if expr is None:
        return set()
    if isinstance(expr, Name): return {expr.name}
    if isinstance(expr, Literal): return set()
    if isinstance(expr, (Field, Property)): return _names(expr.base)
    if isinstance(expr, (Binary, Compare)):
        return _names(expr.left) | _names(expr.right)
    if isinstance(expr, Logical):
        return _names(expr.left) | (_names(expr.right) if expr.right is not None else set())
    if isinstance(expr, Conditional):
        return _names(expr.condition) | _names(expr.then_expr) | _names(expr.else_expr)
    if isinstance(expr, Call):
        out = set()
        for arg in expr.args: out |= _names(arg)
        return out
    return set()


def _strategies(goal: GoalIR) -> tuple[GoalStrategy, ...]:
    if goal.kind == "transition":
        return (
            GoalStrategy("goal-directed-transition", True, "finite candidate transitions with deterministic target distance and constraints"),
            GoalStrategy("search-based-transition", False, "requires a backend-provided general search strategy"),
        )
    if goal.kind == "select":
        return (
            GoalStrategy("scan", True, "always semantics-preserving for a finite collection"),
            GoalStrategy("indexed", False, "requires a proven suitable index; none is declared"),
            GoalStrategy("parallel-reduction", False, "requires a parallel backend; not enabled in the reference runtime"),
        )
    if goal.kind == "path":
        return (
            GoalStrategy("dijkstra", True, "goal specifies minimum additive path cost"),
            GoalStrategy("cost-aware search", True, "semantics-compatible search strategy"),
        )
    if goal.kind == "satisfy":
        return (
            GoalStrategy("constraint-propagation", True, "bounded integer domains and linear constraints can be narrowed deterministically before enumeration"),
            GoalStrategy("enumeration", True, "finite integer domains are explicitly bounded"),
        )
    return (GoalStrategy("reference-execution", True, "fallback reference semantics"),)


def analyze_goals(module) -> list[GoalPlan]:
    goals = lower_goals(module)
    results = {g.result for g in goals}
    plans: list[GoalPlan] = []
    for g in goals:
        refs: set[str] = set()
        if g.source: refs.add(g.source)
        if g.target is not None: refs |= _names(g.target)
        for candidate in g.candidates: refs |= _names(candidate)
        for expr in g.constraints: refs |= _names(expr)
        if g.key is not None: refs |= _names(g.key)
        refs.discard(g.result)
        goal_deps = refs & results
        external = refs - results
        external.discard("row")
        strategies = _strategies(g)
        selected = next((s.name for s in strategies if s.applicable), "none")
        plans.append(GoalPlan(g, tuple(sorted(goal_deps)), tuple(sorted(external)), not goal_deps, strategies, selected))
    return plans


def build_execution_plan(module) -> ExecutionPlan:
    """Build the deterministic plan consumed by the reference runtime."""
    return ExecutionPlan(tuple(analyze_goals(module)))


def format_goal_plan(plans_or_plan) -> str:
    plans = plans_or_plan.goals if isinstance(plans_or_plan, ExecutionPlan) else plans_or_plan
    lines = ["goal.plan {"]
    if not plans: lines.append("  // no goals")
    for p in plans:
        g = p.goal
        lines.append(f'  goal "{g.result}" kind={g.kind}')
        lines.append("    dependencies = " + (", ".join(p.dependencies) if p.dependencies else "none"))
        lines.append(f"    independent = {'yes' if p.independent else 'no'}")
        lines.append("    external_sources = " + (", ".join(p.external_sources) if p.external_sources else "none"))
        lines.append("    strategy_candidates = " + ", ".join(p.strategy_candidates))
        lines.append("    strategy_selected = " + p.selected_strategy)
        for s in p.strategies:
            state = "applicable" if s.applicable else "unavailable"
            lines.append(f"    strategy.{s.name} = {state}: {s.reason}")
    lines.append("}")
    return "\n".join(lines)
