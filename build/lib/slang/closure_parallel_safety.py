"""Closure-aware parallel safety helpers for S-Lang 1.8.35."""
from __future__ import annotations


def function_capture_contracts(module):
    """Return ``function -> captured names`` from the canonical effect analysis."""
    from .function_effects import analyze_function_effects
    return {summary.function: tuple(summary.captures) for summary in analyze_function_effects(module)}


def expression_captured_names(expr, module, aliases=None):
    """Resolve captured names used by function-valued expressions/calls.

    The result is intentionally conservative: aliases are followed and every
    referenced user function contributes its lexical captures.
    """
    if expr is None:
        return set()
    aliases = aliases or {}
    captures = function_capture_contracts(module)

    def resolve(name):
        seen = set()
        while name in aliases and name not in seen:
            seen.add(name)
            name = aliases[name]
        return name

    def walk(obj):
        from .ast import Name, Call, Binary, Compare, Logical, Field, Property, Conditional
        if obj is None:
            return set()
        if isinstance(obj, Name):
            return set(captures.get(resolve(obj.name), ()))
        if isinstance(obj, Call):
            out = set(captures.get(resolve(obj.name), ()))
            for arg in obj.args:
                out.update(walk(arg))
            return out
        if isinstance(obj, (Binary, Compare, Logical)):
            return walk(obj.left) | walk(getattr(obj, 'right', None))
        if isinstance(obj, (Field, Property)):
            return walk(obj.base)
        if isinstance(obj, Conditional):
            return walk(obj.condition) | walk(obj.then_expr) | walk(obj.else_expr)
        return set()

    return walk(expr)
