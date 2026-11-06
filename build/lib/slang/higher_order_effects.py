"""Unified higher-order effect propagation for S-Lang 1.6.0.

Collection and functional constructs inherit effects from the function-valued
expressions they execute. This module keeps that rule centralized so map,
where, reduce, aggregate, compose, and apply use the same deterministic model.
"""
from __future__ import annotations
from dataclasses import dataclass
from .ast import Name, Call, Binary, Compare, Logical, Field, Property, Conditional, Expr, Predicate, SortSpec

@dataclass(frozen=True)
class HigherOrderEffectSummary:
    operation: str
    node: str
    effects: tuple[str, ...]
    sources: tuple[str, ...]
    parallel_safe: bool
    reason: str


def _resolve_alias(name, aliases):
    seen = set()
    while name in aliases and name not in seen:
        seen.add(name)
        name = aliases[name]
    return name


def _expr_effects(expr, function_effects, aliases, effect_specs):
    if expr is None:
        return set(), set()
    if isinstance(expr, (Predicate, SortSpec)):
        return _expr_effects(expr.expr, function_effects, aliases, effect_specs)
    if isinstance(expr, Name):
        target = _resolve_alias(expr.name, aliases)
        return set(function_effects.get(target, ())), {target} if target in function_effects else set()
    if isinstance(expr, Call):
        effects, sources = set(function_effects.get(expr.name, ())), set()
        target = _resolve_alias(expr.name, aliases)
        if target != expr.name:
            effects.update(function_effects.get(target, ()))
        for variable, index in effect_specs.get(target, ()):
            if index < len(expr.args):
                arg_effects, arg_sources = _expr_effects(expr.args[index], function_effects, aliases, effect_specs)
                effects.update(arg_effects)
                sources.update(arg_sources)
        # All higher-order arguments contribute to the enclosing expression.
        # This covers compose/apply and future higher-order builtins uniformly.
        if expr.name in {"compose", "apply", "map", "where", "reduce", "aggregate", "filter", "sort"}:
            for arg in expr.args:
                ae, ass = _expr_effects(arg, function_effects, aliases, effect_specs)
                effects.update(ae); sources.update(ass)
        else:
            for arg in expr.args:
                ae, ass = _expr_effects(arg, function_effects, aliases, effect_specs)
                effects.update(ae); sources.update(ass)
        return effects, sources
    if isinstance(expr, (Binary, Compare, Logical)):
        a, sa = _expr_effects(expr.left, function_effects, aliases, effect_specs)
        b, sb = _expr_effects(getattr(expr, 'right', None), function_effects, aliases, effect_specs)
        return a | b, sa | sb
    if isinstance(expr, (Field, Property)):
        return _expr_effects(expr.base, function_effects, aliases, effect_specs)
    if isinstance(expr, Conditional):
        a, sa = _expr_effects(expr.condition, function_effects, aliases, effect_specs)
        b, sb = _expr_effects(expr.then_expr, function_effects, aliases, effect_specs)
        c, sc = _expr_effects(expr.else_expr, function_effects, aliases, effect_specs)
        return a | b | c, sa | sb | sc
    return set(), set()


def _aliases(module):
    aliases = {}
    for binding in getattr(module, 'bindings', []):
        expr = getattr(binding, 'expr', None)
        if isinstance(expr, Name):
            aliases[binding.name] = expr.name
        elif isinstance(expr, Call):
            # Keep the binding name intact. Its instantiated returned-function
            # effect is materialized separately by _binding_effects; resolving
            # the alias directly to `factory.__return__` would lose generic
            # effect-variable substitution.
            continue
    changed = True
    while changed:
        changed = False
        for name, target in list(aliases.items()):
            resolved = _resolve_alias(target, aliases)
            if resolved != target:
                aliases[name] = resolved; changed = True
    return aliases


def _effect_specs(module):
    specs = {}
    for fn in getattr(module, 'functions', []):
        for index, (_, ref) in enumerate(getattr(fn, 'parameters', [])):
            if getattr(ref, 'name', None) != 'Function':
                continue
            args = list(getattr(ref, 'args', ()))
            if not args:
                continue
            while args and not getattr(args[-1], 'args', ()) and len(args[-1].name) == 1 and args[-1].name.isupper():
                marker = '$' + args.pop().name
                specs.setdefault(fn.name, []).append((marker, index))
    return {name: tuple(values) for name, values in specs.items()}



def _returned_call_effects(call, function_effects, aliases, effect_specs):
    """Instantiate a higher-order function's returned closure contract.

    Generic return contracts may contain effect variables such as ``$E``.
    Resolve each variable from the corresponding function-valued argument so a
    binding like ``let lifted = lift(load)`` carries ``io`` rather than the
    unresolved polymorphic marker.
    """
    target = _resolve_alias(call.name, aliases)
    raw = function_effects.get(target + '.__return__', function_effects.get(call.name + '.__return__', ()))
    if not raw:
        return set()
    specs = dict(effect_specs.get(target, effect_specs.get(call.name, ())))
    out = set()
    for effect in raw:
        if isinstance(effect, str) and effect.startswith('$'):
            index = specs.get(effect)
            if index is not None and index < len(call.args):
                arg_effects, _ = _expr_effects(call.args[index], function_effects, aliases, effect_specs)
                out.update(arg_effects)
            else:
                out.add(effect)
        else:
            out.add(effect)
    return out


def _binding_effects(module, function_effects, aliases, effect_specs):
    """Infer instantiated effects for function-valued local bindings."""
    result = {}
    for binding in getattr(module, 'bindings', []):
        expr = getattr(binding, 'expr', None)
        if isinstance(expr, Call):
            effects = _returned_call_effects(expr, function_effects, aliases, effect_specs)
            if effects:
                result[binding.name] = tuple(sorted(effects))
        elif isinstance(expr, Name):
            target = _resolve_alias(expr.name, aliases)
            effects = function_effects.get(target, function_effects.get(expr.name, ()))
            if effects:
                result[binding.name] = tuple(effects)
    return result

def analyze_higher_order_effects(module, function_effects) -> tuple[HigherOrderEffectSummary, ...]:
    aliases = _aliases(module)
    specs = _effect_specs(module)
    # Materialize instantiated contracts for local function-valued bindings
    # before analyzing map/where/reduce/etc. This is the bridge between a
    # generic higher-order factory and a later alias or pipeline operation.
    instantiated = _binding_effects(module, function_effects, aliases, specs)
    function_effects = dict(function_effects)
    function_effects.update(instantiated)
    summaries = []
    groups = (
        ('where', getattr(module, 'filters', []), 'predicate'),
        ('sort', getattr(module, 'sorts', []), 'spec'),
        ('map', getattr(module, 'maps', []), 'expr'),
        ('aggregate', getattr(module, 'aggregates', []), 'expr'),
        ('reduce', getattr(module, 'reduces', []), 'expr'),
    )
    for operation, items, field in groups:
        for item in items:
            expr = getattr(item, field, None)
            # SortSpec is not a callable expression; no effect unless it embeds one.
            effects, sources = _expr_effects(expr, function_effects, aliases, specs)
            ordered = tuple(sorted(effects))
            unsafe = {'state-write', 'io', 'external'} & effects
            summaries.append(HigherOrderEffectSummary(operation, item.result, ordered, tuple(sorted(sources)), not unsafe, 'pure higher-order operation' if not effects else 'inherits effects from function-valued expression'))
    return tuple(summaries)


def format_higher_order_effects(summaries):
    lines = ['higher-order.effects {']
    for s in summaries:
        lines.append(f'  {s.operation} {s.node}:')
        lines.append('    effects = ' + (', '.join(s.effects) if s.effects else 'pure'))
        lines.append('    sources = ' + (', '.join(s.sources) if s.sources else 'none'))
        lines.append('    parallel_safe = ' + ('yes' if s.parallel_safe else 'no'))
        lines.append('    reason = ' + s.reason)
    lines.append(f'  operations = {len(summaries)}')
    lines.append('  model = unified-higher-order-effect-propagation')
    lines.append('  deterministic = yes')
    lines.append('}')
    return '\n'.join(lines)
