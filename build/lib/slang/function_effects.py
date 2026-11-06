"""Function-level effect contracts for S-Lang 1.6.0.

Function effects are inferred from the function body and propagated through the
user-defined call graph. The result is deterministic and backend-neutral.
"""
from __future__ import annotations
from dataclasses import dataclass, fields, is_dataclass
from .ast import Name, Call, Expr, LetOp, ReturnOp, IfOp
from .effect_analysis import PURE, STATE_READ, STATE_WRITE, IO, EXTERNAL

_EFFECT_ORDER = {PURE: 0, STATE_READ: 1, STATE_WRITE: 2, IO: 3, EXTERNAL: 4}
_BUILTIN_EFFECTS = {
    "read_csv": {IO}, "write_csv": {IO}, "read_file": {IO}, "write_file": {IO}, "read": {IO}, "write": {IO},
    "read_lines": {IO}, "list_files": {IO}, "list_directories": {IO}, "remove_file": {IO}, "remove_directory_tree": {IO}, "copy_file": {IO}, "move_file": {IO}, "make_directories": {IO}, "write_lines": {IO}, "exists": {IO}, "file_size": {IO}, "is_file": {IO}, "is_directory": {IO}, "list_directory": {IO}, "arguments": {IO}, "environment": {IO}, "run_process": {IO}, "run_program": {IO}, "run_program_with_environment": {IO}, "current_directory": {IO}, "platform_name": {IO}, "process_id": {IO}, "sleep_seconds": {IO}, "home_directory": {IO}, "temp_directory": {IO}, "executable_path": {IO}, "command_exists": {IO}, "show": {IO},
}

@dataclass(frozen=True)
class FunctionEffectSummary:
    function: str
    effects: tuple[str, ...]
    purity: str
    reorderable: bool
    parallel_safe: bool
    order_sensitive: bool
    calls: tuple[str, ...]
    reason: str
    effect_parameters: tuple[str, ...] = ()
    captures: tuple[str, ...] = ()
    returned_function_effects: tuple[str, ...] = ()

    @property
    def effectful(self) -> bool:
        return bool(self.effects)


def _walk(obj):
    if obj is None:
        return
    if isinstance(obj, (str, bytes, int, float, bool)):
        return
    if isinstance(obj, dict):
        for v in obj.values(): yield from _walk(v)
        return
    if isinstance(obj, (tuple, list, set, frozenset)):
        for v in obj: yield from _walk(v)
        return
    if is_dataclass(obj):
        yield obj
        for f in fields(obj):
            yield from _walk(getattr(obj, f.name))


def _parameter_effect_variables(fn):
    result = {}
    for name, ref in getattr(fn, 'parameters', []):
        if ref is None or getattr(ref, 'name', None) != 'Function':
            continue
        args = list(getattr(ref, 'args', ()))
        markers = []
        effect_names = {'pure', 'state-read', 'state-write', 'io', 'external'}
        while args and not getattr(args[-1], 'args', ()) and (args[-1].name in effect_names or (len(args[-1].name) == 1 and args[-1].name.isupper())):
            marker = args.pop().name
            if marker not in effect_names:
                marker = '$' + marker
            markers.append(marker)
        if markers:
            result[name] = tuple(reversed(markers))
    return result


def _module_globals(module):
    names = {getattr(st, 'name', st) for st in getattr(module, 'states', ())}
    names.update(fn.name for fn in getattr(module, 'functions', ()))
    names.update(b.name for b in getattr(module, 'bindings', ()))
    return names


def _body_local_names(body):
    names = set()
    for stmt in body:
        if isinstance(stmt, LetOp):
            names.add(stmt.name)
        elif stmt.__class__.__name__ == 'FunctionDecl':
            names.add(stmt.name)
    return names


def _collect_functions(module):
    entries = []

    def visit(fn, lexical_scope, qualified):
        entries.append((qualified, fn, set(lexical_scope)))
        scope = set(lexical_scope)
        scope.update(name for name, _ in fn.parameters)
        for stmt in fn.body:
            if stmt.__class__.__name__ == 'FunctionDecl':
                visit(stmt, scope, f'{qualified}.{stmt.name}')
                scope.add(stmt.name)
            elif isinstance(stmt, LetOp):
                scope.add(stmt.name)
            elif stmt.__class__.__name__ == 'IfOp':
                # Function declarations inside branches inherit the scope at
                # branch entry; branch-local lets do not leak outward.
                for branch in (stmt.then_body, stmt.else_body):
                    branch_scope = set(scope)
                    for child in branch:
                        if child.__class__.__name__ == 'FunctionDecl':
                            visit(child, branch_scope, f'{qualified}.{child.name}')
                        elif isinstance(child, LetOp):
                            branch_scope.add(child.name)

    for fn in getattr(module, 'functions', ()):
        visit(fn, set(), fn.name)
    return entries


def _analyze_one(fn, lexical_scope, state_names):
    effects = set()
    calls = set()
    captures = set()
    parameter_names = {name for name, _ in fn.parameters}
    aliases = {}

    for stmt in fn.body:
        if isinstance(stmt, LetOp) and isinstance(stmt.expr, Name):
            aliases[stmt.name] = stmt.expr.name

    def resolve(name):
        seen = set()
        while name in aliases and name not in seen:
            seen.add(name)
            name = aliases[name]
        return name

    parameter_effects = _parameter_effect_variables(fn)
    outer = set(lexical_scope) - parameter_names

    def observe(expr):
        if expr is None:
            return
        for obj in _walk(expr):
            if isinstance(obj, Name):
                name = obj.name
                if name in outer:
                    captures.add(name)
                if name in state_names and name not in parameter_names:
                    effects.add(STATE_READ)
            elif isinstance(obj, Call):
                target = resolve(obj.name)
                calls.add(target)
                effects.update(_BUILTIN_EFFECTS.get(target, set()))
                if target in parameter_effects:
                    effects.update(parameter_effects[target])
                if obj.name in {"compose", "apply"}:
                    for arg in obj.args:
                        if isinstance(arg, Name):
                            arg_target = resolve(arg.name)
                            calls.add(arg_target)
                            effects.update(_BUILTIN_EFFECTS.get(arg_target, set()))

    def observe_body(body):
        for stmt in body:
            # Nested functions are separate effect contracts. Merely creating
            # an IO-using closure does not execute its body.
            if stmt.__class__.__name__ == 'FunctionDecl':
                continue
            if isinstance(stmt, LetOp):
                observe(stmt.expr)
            elif isinstance(stmt, ReturnOp):
                observe(stmt.expr)
            elif stmt.__class__.__name__ == 'IfOp':
                observe(stmt.condition)
                observe_body(stmt.then_body)
                observe_body(stmt.else_body)
            elif stmt.__class__.__name__ == 'SetStateOp':
                effects.add(STATE_WRITE)
                observe(stmt.expr)
            elif isinstance(stmt, Expr):
                observe(stmt)

    observe_body(fn.body)
    return effects, calls, captures


def _returned_function_target(fn):
    """Find a locally declared function returned by a factory, if any."""
    local_functions = {stmt.name for stmt in fn.body if stmt.__class__.__name__ == 'FunctionDecl'}
    aliases = {}
    for stmt in fn.body:
        if isinstance(stmt, LetOp) and isinstance(stmt.expr, Name):
            aliases[stmt.name] = stmt.expr.name
    for stmt in reversed(fn.body):
        if isinstance(stmt, ReturnOp) and isinstance(stmt.expr, Name):
            target = stmt.expr.name
            seen = set()
            while target in aliases and target not in seen:
                seen.add(target)
                target = aliases[target]
            if target in local_functions:
                return target
    return None


def analyze_function_effects(module) -> tuple[FunctionEffectSummary, ...]:
    entries = _collect_functions(module)
    state_names = _module_globals(module) & {getattr(st, 'name', st) for st in getattr(module, 'states', ())}
    direct = {}
    for qualified, fn, lexical in entries:
        direct[qualified] = _analyze_one(fn, lexical, state_names)

    by_short = {}
    for qualified in direct:
        by_short.setdefault(qualified.rsplit('.', 1)[-1], []).append(qualified)

    def resolve_callee(caller, callee):
        if callee in direct:
            return callee
        parts = caller.split('.')
        for depth in range(len(parts), 0, -1):
            candidate = '.'.join(parts[:depth] + [callee])
            if candidate in direct:
                return candidate
        matches = by_short.get(callee, ())
        return matches[0] if len(matches) == 1 else None

    summaries = {name: set(value[0]) for name, value in direct.items()}
    changed = True
    while changed:
        changed = False
        for name, (_, calls, _) in direct.items():
            for callee in calls:
                target = resolve_callee(name, callee)
                if target is None:
                    continue
                before = len(summaries[name])
                summaries[name].update(summaries[target])
                changed |= len(summaries[name]) != before

    result = []
    for name in sorted(direct):
        effects = tuple(sorted(summaries[name], key=lambda x: (_EFFECT_ORDER.get(x, 99), x)))
        calls = tuple(sorted(direct[name][1]))
        captures = tuple(sorted(direct[name][2]))
        effect_parameters = tuple(sorted(e for e in effects if isinstance(e, str) and e.startswith('$')))
        unsafe = {STATE_WRITE, IO, EXTERNAL} & set(effects)
        reorderable = not unsafe
        parallel_safe = not unsafe
        order_sensitive = bool(unsafe)
        if not effects:
            purity, reason = 'pure', 'function body and captured values have no observable effects'
        elif effect_parameters and not unsafe and set(effects) == set(effect_parameters):
            purity, reason = 'effect-polymorphic', 'effect is inherited from a higher-order function parameter'
        elif STATE_READ in effects and not unsafe:
            purity, reason = 'state-dependent', 'function reads state or captured state'
        else:
            purity, reason = 'effectful', 'called operations, captured state, or the function body have observable effects'
        returned = ()
        if '.' not in name:
            fn_obj = next(fn for q, fn, _ in entries if q == name)
            target = _returned_function_target(fn_obj)
            if target is not None:
                nested = f'{name}.{target}'
                returned = tuple(sorted(summaries.get(nested, ()), key=lambda x: (_EFFECT_ORDER.get(x, 99), x)))
            else:
                # A higher-order function may return one of its function-valued
                # parameters directly (for example `lift<E>(f: Function<...,E>)
                # -> Function<...,E>: return f`). In that case the returned
                # closure contract is effect-polymorphic and must survive the
                # factory call.
                parameter_effects = _parameter_effect_variables(fn_obj)
                for stmt in reversed(fn_obj.body):
                    if isinstance(stmt, ReturnOp) and isinstance(stmt.expr, Name):
                        marker_list = parameter_effects.get(stmt.expr.name)
                        if marker_list:
                            returned = tuple(marker_list)
                        break
        result.append(FunctionEffectSummary(name, effects, purity, reorderable, parallel_safe, order_sensitive, calls, reason, effect_parameters, captures, returned))
    return tuple(result)

def format_function_effects(summaries: tuple[FunctionEffectSummary, ...]) -> str:
    lines = ["function.effects {"]
    for s in summaries:
        lines.append(f"  function {s.function}:")
        lines.append("    effects = " + (", ".join(s.effects) if s.effects else "pure"))
        lines.append("    purity = " + s.purity)
        lines.append("    calls = " + (", ".join(s.calls) if s.calls else "none"))
        lines.append("    effect_parameters = " + (", ".join(s.effect_parameters) if s.effect_parameters else "none"))
        lines.append("    captures = " + (", ".join(s.captures) if s.captures else "none"))
        lines.append("    returned_function_effects = " + (", ".join(s.returned_function_effects) if s.returned_function_effects else "none"))
        lines.append("    reorderable = " + ("yes" if s.reorderable else "no"))
        lines.append("    parallel_safe = " + ("yes" if s.parallel_safe else "no"))
        lines.append("    reason = " + s.reason)
    lines.append(f"  functions = {len(summaries)}")
    lines.append("  model = inferred-function-effect-contract")
    lines.append("  deterministic = yes")
    lines.append("}")
    return "\n".join(lines)
