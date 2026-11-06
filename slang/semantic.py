from __future__ import annotations
from dataclasses import dataclass
from difflib import get_close_matches
from .ast import Expr, Literal, Name, Field, Binary, Compare, Logical, Conditional, Call, Property, LetOp, ReturnOp, IfOp, LocalCollectionOp
from .ast import source_span_of
from .diagnostics import DiagnosticRelatedSpan
from .diagnostics import source_location
from .types import Type, NUMBER, BOOLEAN, TEXT, ANY, RECORD, quantity_type, list_type, entity_type, add_types, sub_types, mul_types, div_types, same_or_any, type_var, generic_match, unify_types, substitute_type, function_type, is_function, function_result, function_params, function_effects
from .ast import TypeRef, FunctionDecl
from .stdlib.registry import signatures as stdlib_signatures


def _semantic_error(message: str, code: str = "E2000", **data) -> TypeError:
    exc = TypeError(message)
    exc.diagnostic_code = code
    if data:
        exc.diagnostic_data = data
    return exc

@dataclass
class TypeEnv:
    names: dict[str, Type]
    fields: dict[str, dict[str, Type]]
    properties: dict[str, dict[str, Type]]
    functions: dict[str, tuple[tuple[Type, ...], Type]] = None
    record_params: dict[str, tuple[str, ...]] = None
    function_effect_contracts: dict[str, tuple[str, ...]] = None
    scope_prefix: str = ''

    def field_type(self, base: Type, name: str) -> Type:
        if base.name in ('Entity', 'Record') and base.args:
            type_name = base.args[0].name
            table = self.fields.get(type_name, {})
            if name in table:
                params = (self.record_params or {}).get(type_name, ())
                actual_args = base.args[0].args
                if params and actual_args:
                    bindings = {('$' + param): actual for param, actual in zip(params, actual_args)}
                    return substitute_type(table[name], bindings)
                return table[name]
        if base.name == 'Row':
            table = self.fields.get('Row', {})
            if name in table: return table[name]
        raise _semantic_error(f"unknown field '{name}' on {base}", "E2005", field=name, base_type=str(base))


def _nested_decl_type(ref):
    if ref is None:
        return ANY
    name = ref.name
    aliases = {
        'Number': NUMBER, 'Boolean': BOOLEAN, 'Text': TEXT, 'Any': ANY,
        'Record': RECORD, 'List': Type('List'), 'Entity': Type('Entity'), 'Function': Type('Function'),
    }
    if not ref.args:
        return aliases.get(name, Type(name))
    args = tuple(_nested_decl_type(arg) for arg in ref.args)
    if name == 'List':
        return list_type(args[0] if args else ANY)
    if name == 'Function':
        effect_names = {'pure', 'state-read', 'state-write', 'io', 'external'}
        raw = list(getattr(ref, 'args', ()))
        effects = []
        while raw and (raw[-1].name in effect_names or raw[-1].name.startswith('E')) and not raw[-1].args:
            marker = raw.pop().name
            effects.insert(0, '$' + marker if marker.startswith('E') else marker)
        args = tuple(_nested_decl_type(a) for a in raw)
        return function_type(args[:-1], args[-1], tuple(effects) if effects else None) if args else Type('Function')
    return Type(name, args=args)

def _register_local_function(stmt: FunctionDecl, env: TypeEnv):
    if stmt.name in env.names or stmt.name in (env.functions or {}):
        raise _semantic_error(f"duplicate local function '{stmt.name}'", "E2000", name=stmt.name, construct="duplicate_local_function")
    params = tuple(_nested_decl_type(ref) for _, ref in stmt.parameters)
    # Untyped nested parameters are intentionally rejected here rather than
    # guessing from the closure.  This keeps closure typing deterministic.
    for (name, ref), typ in zip(stmt.parameters, params):
        if ref is None:
            raise TypeError(f"cannot infer parameter type for nested function '{stmt.name}({name})'; add an explicit type annotation")
    qualified = f"{env.scope_prefix}.{stmt.name}" if env.scope_prefix else stmt.name
    contracts = env.function_effect_contracts or {}
    contract = contracts.get(qualified, ())
    local = TypeEnv(
        names=dict(env.names), fields=env.fields, properties=env.properties,
        functions=dict(env.functions or {}), record_params=env.record_params,
        function_effect_contracts=contracts, scope_prefix=qualified
    )
    local.names.update({name: typ for (name, _), typ in zip(stmt.parameters, params)})
    # Register first so recursion is statically valid.
    declared_ret = _nested_decl_type(stmt.return_type) if stmt.return_type else None
    signature = (params, declared_ret or ANY)
    env.functions[stmt.name] = signature
    local.functions[stmt.name] = signature
    inferred = infer_block(stmt.body, local)
    ret = declared_ret or inferred
    # An unannotated Function effect contract is completed from the returned
    # function value. Explicit effect contracts remain checked normally.
    if declared_ret is not None and is_function(declared_ret) and declared_ret.effects is None and is_function(inferred):
        ret = function_type(function_params(declared_ret), function_result(declared_ret), function_effects(inferred))
    if not unify_types(ret, inferred, {}):
        raise _semantic_error(f"nested function '{stmt.name}' returns {inferred}, declared {ret}", expected_type=str(ret), actual_type=str(inferred), construct="function_return")
    env.functions[stmt.name] = (params, ret)
    local.functions[stmt.name] = (params, ret)
    env.names[stmt.name] = function_type(params, ret, contract)
    return ret


def _infer_impl(expr: Expr, env: TypeEnv) -> Type:
    if isinstance(expr, Literal):
        if isinstance(expr.value, bool): return BOOLEAN
        if isinstance(expr.value, (int, float)): return NUMBER
        if isinstance(expr.value, str): return TEXT
        if isinstance(expr.value, dict): return RECORD
        if isinstance(expr.value, list):
            if not expr.value: return list_type(ANY)
            item_types=[infer(item, env) for item in expr.value]
            first = item_types[0]
            bindings = {}
            for item_type in item_types[1:]:
                if not generic_match(first, item_type, bindings):
                    raise TypeError(f'list literal elements must have compatible types, got {item_types}')
            return list_type(substitute_type(first, bindings))
        # Quantity-like objects deliberately duck-type by exposing dim().
        if hasattr(expr.value, 'dim'):
            return quantity_type(expr.value.dim())
        return ANY
    if isinstance(expr, Name):
        if expr.name in env.names:
            return env.names[expr.name]
        if expr.name in (env.functions or {}):
            params, result = env.functions[expr.name]
            return function_type(params, result)
        error = _semantic_error(f"unknown name '{expr.name}'", "E2001", name=expr.name)
        # Offer a restrained typo hint only when there is one strong match.
        # This improves beginner-facing diagnostics without changing the stable
        # error message or structured payload consumed by editors and tooling.
        candidates = set(env.names) | set(env.functions or {}) | set(stdlib_signatures())
        candidates.discard(expr.name)
        matches = get_close_matches(expr.name, sorted(candidates), n=2, cutoff=0.78)
        if len(matches) == 1:
            error.hint = f"did you mean '{matches[0]}'? Check the spelling or declare '{expr.name}' before using it."
        elif len(matches) > 1:
            # Avoid confidently suggesting one name when multiple candidates
            # are similarly plausible.
            error.hint = "check the spelling; possible names: " + ", ".join(repr(name) for name in matches)
        raise error
    if isinstance(expr, Field):
        base = infer(expr.base, env)
        if base.name == 'Any' or (base.name == 'Record' and not base.args): return ANY
        return env.field_type(base, expr.name)
    if isinstance(expr, Property):
        base = infer(expr.base, env)
        if base.name == 'Any' or (base.name == 'Record' and not base.args): return ANY
        key = base.args[0].name if base.name in ('Entity', 'Record') and base.args else base.name
        # A dot access can name either a declared field or a computed property.
        field_table = env.fields.get(key, {})
        if expr.name in field_table:
            typ = field_table[expr.name]
            params = (env.record_params or {}).get(key, ())
            actual_args = base.args[0].args if base.name in ('Entity', 'Record') and base.args else ()
            if params and actual_args:
                bindings = {('$' + param): actual for param, actual in zip(params, actual_args)}
                return substitute_type(typ, bindings)
            return typ
        table = env.properties.get(key, {})
        if expr.name not in table: raise _semantic_error(f"unknown field '{expr.name}' on {base}", "E2005", field=expr.name, base_type=str(base))
        return table[expr.name]
    if isinstance(expr, Binary):
        a, b = infer(expr.left, env), infer(expr.right, env)
        if expr.op == '+': return add_types(a, b)
        if expr.op == '-': return sub_types(a, b)
        if expr.op == '*': return mul_types(a, b)
        if expr.op == '/': return div_types(a, b)
        if expr.op == '%':
            if a != NUMBER or b != NUMBER:
                raise _semantic_error('operator % requires Number operands', 'E2004', operator='%')
            return NUMBER
        if expr.op == '^':
            if b != NUMBER: raise _semantic_error('exponent must be Number', 'E2004', expected_type=str(NUMBER), actual_type=str(b), operator='^')
            return a
        raise TypeError(f"unknown binary operator '{expr.op}'")
    if isinstance(expr, Conditional):
        condition = infer(expr.condition, env)
        if condition != BOOLEAN:
            raise _semantic_error(f'conditional condition must be Boolean, got {condition}', 'E2006', expected_type=str(BOOLEAN), actual_type=str(condition), construct='conditional')
        then_type = infer(expr.then_expr, env)
        else_type = infer(expr.else_expr, env)
        bindings = {}
        if not generic_match(then_type, else_type, bindings):
            raise _semantic_error(f'conditional branches must have compatible types, got {then_type} and {else_type}', 'E2000', expected_type=str(then_type), actual_type=str(else_type), construct='conditional')
        return substitute_type(then_type, bindings)
    if isinstance(expr, Compare):
        a, b = infer(expr.left, env), infer(expr.right, env)
        if not same_or_any(a, b): raise _semantic_error(f'cannot compare {a} and {b}', 'E2004', expected_type=str(a), actual_type=str(b), operator=expr.op)
        return BOOLEAN
    if isinstance(expr, Logical):
        left = infer(expr.left, env)
        if left != BOOLEAN: raise _semantic_error(f"logical operand must be Boolean, got {left}", 'E2006', expected_type=str(BOOLEAN), actual_type=str(left), operator=expr.op, operand='left')
        if expr.op == 'not': return BOOLEAN
        right = infer(expr.right, env)
        if right != BOOLEAN: raise _semantic_error(f"logical operand must be Boolean, got {right}", 'E2006', expected_type=str(BOOLEAN), actual_type=str(right), operator=expr.op, operand='right')
        if expr.op not in ('and', 'or'): raise TypeError(f"unknown logical operator '{expr.op}'")
        return BOOLEAN
    if isinstance(expr, Call):
        builtins = {
            'len': ((ANY,), NUMBER),
            'contains': ((ANY, ANY), BOOLEAN),
            'join': ((list_type(TEXT), TEXT), TEXT),
            'read': ((TEXT,), TEXT),
            'write': ((TEXT, TEXT), BOOLEAN),
            'read_text': ((TEXT,), TEXT),
            'write_text': ((TEXT, TEXT), BOOLEAN),
            'append_text': ((TEXT, TEXT), BOOLEAN),
            'read_lines': ((TEXT,), list_type(TEXT)),
            'read_json': ((TEXT,), ANY),
            'write_json': ((TEXT, ANY), BOOLEAN),
            'write_lines': ((TEXT, list_type(TEXT)), BOOLEAN),
            'exists': ((TEXT,), BOOLEAN),
            'file_size': ((TEXT,), NUMBER),
            'is_file': ((TEXT,), BOOLEAN),
            'is_directory': ((TEXT,), BOOLEAN),
            'list_directory': ((TEXT,), list_type(TEXT)),
            'list_files': ((TEXT,), list_type(TEXT)),
            'list_directories': ((TEXT,), list_type(TEXT)),
            'make_directory': ((TEXT,), BOOLEAN),
            'remove_directory': ((TEXT,), BOOLEAN),
            'remove_directory_tree': ((TEXT,), BOOLEAN),
            'remove_file': ((TEXT,), BOOLEAN),
            'copy_file': ((TEXT, TEXT), BOOLEAN),
            'move_file': ((TEXT, TEXT), BOOLEAN),
            'make_directories': ((TEXT,), BOOLEAN),
            'basename': ((TEXT,), TEXT),
            'dirname': ((TEXT,), TEXT),
            'extension': ((TEXT,), TEXT),
            'join_path': ((TEXT, TEXT), TEXT),
            'normalize_path': ((TEXT,), TEXT),
            'read_csv': ((TEXT,), list_type(RECORD)),
            'write_csv': ((TEXT, list_type(RECORD)), BOOLEAN),
            'csv_headers': ((list_type(RECORD),), list_type(TEXT)),
            'to_number': ((TEXT,), NUMBER),
            # 1.7 standard library: pure numeric, text, and JSON operations.
            'abs_number': ((NUMBER,), NUMBER),
            'sqrt': ((NUMBER,), NUMBER),
            'floor': ((NUMBER,), NUMBER),
            'ceil': ((NUMBER,), NUMBER),
            'round_number': ((NUMBER,), NUMBER),
            'clamp_number': ((NUMBER, NUMBER, NUMBER), NUMBER),
            'sign_number': ((NUMBER,), NUMBER),
            'pow_number': ((NUMBER, NUMBER), NUMBER),
            'min_of_numbers': ((NUMBER, NUMBER), NUMBER),
            'max_of_numbers': ((NUMBER, NUMBER), NUMBER),
            'lerp_number': ((NUMBER, NUMBER, NUMBER), NUMBER),
            'log_number': ((NUMBER, NUMBER), NUMBER),
            'exp_number': ((NUMBER,), NUMBER),
            'exp2_number': ((NUMBER,), NUMBER),
            'cbrt_number': ((NUMBER,), NUMBER),
            'log10_number': ((NUMBER,), NUMBER),
            'log2_number': ((NUMBER,), NUMBER),
            'mod_number': ((NUMBER, NUMBER), NUMBER),
            'hypot_number': ((NUMBER, NUMBER), NUMBER),
            'degrees_number': ((NUMBER,), NUMBER),
            'radians_number': ((NUMBER,), NUMBER),
            'sin_number': ((NUMBER,), NUMBER),
            'cos_number': ((NUMBER,), NUMBER),
            'tan_number': ((NUMBER,), NUMBER),
            'asin_number': ((NUMBER,), NUMBER),
            'acos_number': ((NUMBER,), NUMBER),
            'atan_number': ((NUMBER,), NUMBER),
            'atan2_number': ((NUMBER, NUMBER), NUMBER),
            'sinh_number': ((NUMBER,), NUMBER),
            'cosh_number': ((NUMBER,), NUMBER),
            'tanh_number': ((NUMBER,), NUMBER),
            'asinh_number': ((NUMBER,), NUMBER),
            'acosh_number': ((NUMBER,), NUMBER),
            'atanh_number': ((NUMBER,), NUMBER),
            'gcd_number': ((NUMBER, NUMBER), NUMBER),
            'lcm_number': ((NUMBER, NUMBER), NUMBER),
            'factorial_number': ((NUMBER,), NUMBER),
            'is_finite_number': ((NUMBER,), BOOLEAN),
            'is_nan_number': ((NUMBER,), BOOLEAN),
            'is_integer_number': ((NUMBER,), BOOLEAN),
            'reciprocal_number': ((NUMBER,), NUMBER),
            'truncate_number': ((NUMBER,), NUMBER),
            'fraction_number': ((NUMBER,), NUMBER),
            'is_even_number': ((NUMBER,), BOOLEAN),
            'is_odd_number': ((NUMBER,), BOOLEAN),
            'trim': ((TEXT,), TEXT),
            'lower': ((TEXT,), TEXT),
            'upper': ((TEXT,), TEXT),
            'starts_with': ((TEXT, TEXT), BOOLEAN),
            'ends_with': ((TEXT, TEXT), BOOLEAN),
            'replace': ((TEXT, TEXT, TEXT), TEXT),
            'split': ((TEXT, TEXT), list_type(TEXT)),
            'contains_text': ((TEXT, TEXT), BOOLEAN),
            'index_of': ((TEXT, TEXT), NUMBER),
            'join_texts': ((list_type(TEXT), TEXT), TEXT),
            'repeat_text': ((TEXT, NUMBER), TEXT),
            'length_text': ((TEXT,), NUMBER),
            'substring_text': ((TEXT, NUMBER, NUMBER), TEXT),
            'char_at_text': ((TEXT, NUMBER), TEXT),
            'pad_left_text': ((TEXT, NUMBER, TEXT), TEXT),
            'pad_right_text': ((TEXT, NUMBER, TEXT), TEXT),
            'count_text': ((TEXT, TEXT), NUMBER),
            'remove_prefix_text': ((TEXT, TEXT), TEXT),
            'remove_suffix_text': ((TEXT, TEXT), TEXT),
            'reverse_text': ((TEXT,), TEXT),
            'json_parse': ((TEXT,), ANY),
            'json_stringify': ((ANY,), TEXT),
            'json_pretty': ((ANY,), TEXT),
            'json_get': ((ANY, TEXT, ANY), ANY),
            'json_has': ((ANY, TEXT), BOOLEAN),
            'json_set': ((ANY, TEXT, ANY), ANY),
            'parse_datetime': ((TEXT, TEXT), TEXT),
            'format_datetime': ((TEXT, TEXT), TEXT),
            'add_seconds_datetime': ((TEXT, NUMBER), TEXT),
            'diff_seconds_datetime': ((TEXT, TEXT), NUMBER),
            'add_days_datetime': ((TEXT, NUMBER), TEXT),
            'add_months_datetime': ((TEXT, NUMBER), TEXT),
            'start_of_day_datetime': ((TEXT,), TEXT),
            'end_of_day_datetime': ((TEXT,), TEXT),
            'date_components_datetime': ((TEXT,), list_type(NUMBER)),
            'is_leap_year': ((NUMBER,), BOOLEAN),
            'days_in_month': ((NUMBER, NUMBER), NUMBER),
            'weekday_datetime': ((TEXT,), NUMBER),
            'week_number_datetime': ((TEXT,), NUMBER),
            'now_utc': ((), TEXT),
            'today_utc': ((), TEXT),
            'current_directory': ((), TEXT),
            'has_environment': ((TEXT,), BOOLEAN),
            'set_environment': ((TEXT, TEXT), BOOLEAN),
            'remove_environment': ((TEXT,), BOOLEAN),
            'platform_name': ((), TEXT),
            'process_id': ((), NUMBER),
            'sleep_seconds': ((NUMBER,), BOOLEAN),
            'home_directory': ((), TEXT),
            'temp_directory': ((), TEXT),
            'executable_path': ((), TEXT),
            'command_exists': ((TEXT,), BOOLEAN),
            'run_process_timeout': ((TEXT, NUMBER), list_type(TEXT)),
            'run_program_timeout': ((TEXT, list_type(TEXT), NUMBER, TEXT), list_type(TEXT)),
            'pluck': ((list_type(RECORD), TEXT), list_type(ANY)),
            'select_fields': ((RECORD, list_type(TEXT)), RECORD),
            'merge_records': ((RECORD, RECORD), RECORD),
            'remove_field': ((RECORD, TEXT), RECORD),
            'group_by': ((list_type(RECORD), TEXT), list_type(RECORD)),
            'group_count': ((list_type(RECORD), TEXT), list_type(RECORD)),
            'group_sum': ((list_type(RECORD), TEXT, TEXT), list_type(RECORD)),
            'group_average': ((list_type(RECORD), TEXT, TEXT), list_type(RECORD)),
            'group_min': ((list_type(RECORD), TEXT, TEXT), list_type(RECORD)),
            'group_max': ((list_type(RECORD), TEXT, TEXT), list_type(RECORD)),
            'frequency': ((list_type(type_var('$T')),), list_type(RECORD)),
            'mode': ((list_type(type_var('$T')),), type_var('$T')),
            'distinct_by': ((list_type(RECORD), TEXT), list_type(RECORD)),
            'join_records': ((list_type(RECORD), list_type(RECORD), TEXT, TEXT), list_type(RECORD)),
            'partition': ((list_type(RECORD), TEXT, ANY), RECORD),
            'order_by': ((list_type(RECORD), TEXT, BOOLEAN), list_type(RECORD)),
            'find_by': ((list_type(RECORD), TEXT, ANY), ANY),
            'count_by': ((list_type(RECORD), TEXT, ANY), NUMBER),
            'window': ((list_type(RECORD), NUMBER, NUMBER), list_type(list_type(RECORD))),
            'rank_by': ((list_type(RECORD), TEXT, BOOLEAN), list_type(RECORD)),
            'top_by': ((list_type(RECORD), TEXT, NUMBER), list_type(RECORD)),
            'bottom_by': ((list_type(RECORD), TEXT, NUMBER), list_type(RECORD)),
            'window_sum': ((list_type(RECORD), TEXT, NUMBER, NUMBER), list_type(RECORD)),
            'window_average': ((list_type(RECORD), TEXT, NUMBER, NUMBER), list_type(RECORD)),
            'group_top_by': ((list_type(RECORD), TEXT, TEXT, NUMBER), list_type(RECORD)),
            'keys': ((RECORD,), list_type(TEXT)),
            'get': ((RECORD, TEXT), ANY),
            'has': ((RECORD, TEXT), BOOLEAN),
            # Generic collection primitives. $T is unified with the actual element type.
            'first': ((list_type(type_var('$T')),), type_var('$T')),
            'last': ((list_type(type_var('$T')),), type_var('$T')),
            'append': ((list_type(type_var('$T')), type_var('$T')), list_type(type_var('$T'))),
            'flatten': ((list_type(list_type(type_var('$T'))),), list_type(type_var('$T'))),
            'distinct': ((list_type(type_var('$T')),), list_type(type_var('$T'))),
            'take': ((list_type(type_var('$T')), NUMBER), list_type(type_var('$T'))),
            'skip': ((list_type(type_var('$T')), NUMBER), list_type(type_var('$T'))),
            'range_numbers': ((NUMBER, NUMBER, NUMBER), list_type(NUMBER)),
            'reverse': ((list_type(type_var('$T')),), list_type(type_var('$T'))),
            'sort_numbers': ((list_type(NUMBER),), list_type(NUMBER)),
            'sum_numbers': ((list_type(NUMBER),), NUMBER),
            'min_number': ((list_type(NUMBER),), NUMBER),
            'max_number': ((list_type(NUMBER),), NUMBER),
            'count_value': ((list_type(type_var('$T')), type_var('$T')), NUMBER),
            'any_true': ((list_type(BOOLEAN),), BOOLEAN),
            'all_true': ((list_type(BOOLEAN),), BOOLEAN),
            'cumulative_sum_numbers': ((list_type(NUMBER),), list_type(NUMBER)),
            'cumulative_product_numbers': ((list_type(NUMBER),), list_type(NUMBER)),
            'cumulative_min_numbers': ((list_type(NUMBER),), list_type(NUMBER)),
            'cumulative_max_numbers': ((list_type(NUMBER),), list_type(NUMBER)),
            'differences_numbers': ((list_type(NUMBER),), list_type(NUMBER)),
            'cumulative_average_numbers': ((list_type(NUMBER),), list_type(NUMBER)),
            'percent_change_numbers': ((list_type(NUMBER),), list_type(NUMBER)),
            'moving_average_numbers': ((list_type(NUMBER), NUMBER), list_type(NUMBER)),
            'normalize_numbers': ((list_type(NUMBER),), list_type(NUMBER)),
            'quantile_number': ((list_type(NUMBER), NUMBER), NUMBER),
            'sum_squares_numbers': ((list_type(NUMBER),), NUMBER),
            'dot_product_numbers': ((list_type(NUMBER), list_type(NUMBER)), NUMBER),
            'l2_norm_numbers': ((list_type(NUMBER),), NUMBER),
            'euclidean_distance_numbers': ((list_type(NUMBER), list_type(NUMBER)), NUMBER),
            'manhattan_distance_numbers': ((list_type(NUMBER), list_type(NUMBER)), NUMBER),
            'cosine_similarity_numbers': ((list_type(NUMBER), list_type(NUMBER)), NUMBER),
            'z_scores_numbers': ((list_type(NUMBER),), list_type(NUMBER)),
            'covariance_numbers': ((list_type(NUMBER), list_type(NUMBER)), NUMBER),
            'correlation_numbers': ((list_type(NUMBER), list_type(NUMBER)), NUMBER),
            'clip_numbers': ((list_type(NUMBER), NUMBER, NUMBER), list_type(NUMBER)),
            'product_numbers': ((list_type(NUMBER),), NUMBER),
            'average_number': ((list_type(NUMBER),), NUMBER),
            'median_number': ((list_type(NUMBER),), NUMBER),
            'variance_number': ((list_type(NUMBER),), NUMBER),
            'stddev_number': ((list_type(NUMBER),), NUMBER),
            'normalize_number': ((NUMBER, NUMBER, NUMBER), NUMBER),
            'remap_number': ((NUMBER, NUMBER, NUMBER, NUMBER, NUMBER), NUMBER),
            # 1.12.2 collection slicing is exposed through the stdlib registry.
            'chunk': ((list_type(type_var('$T')), NUMBER), list_type(list_type(type_var('$T')))),
            'pairwise': ((list_type(type_var('$T')),), list_type(list_type(type_var('$T')))),
        }
        sigs = dict(builtins)
        # Pure standard-library signatures are maintained in one registry.
        # Keep the legacy table above for core/runtime primitives and compatibility.
        sigs.update(stdlib_signatures())
        sigs.update(env.functions or {})
        if expr.name == 'compose':
            if len(expr.args) != 2:
                raise TypeError("function 'compose' expects two Function arguments")
            outer = infer(expr.args[0], env)
            inner = infer(expr.args[1], env)
            if not is_function(outer) or not is_function(inner):
                raise TypeError(f"compose expects Function values, got {outer} and {inner}")
            outer_params = function_params(outer)
            inner_params = function_params(inner)
            if len(outer_params) != 1 or len(inner_params) != 1:
                raise TypeError("compose currently requires unary functions")
            bindings = {}
            if not generic_match(outer_params[0], function_result(inner), bindings):
                raise TypeError(f"compose type mismatch: inner returns {function_result(inner)}, outer expects {outer_params[0]}")
            outer_params = tuple(substitute_type(p, bindings) for p in outer_params)
            outer_result = substitute_type(function_result(outer), bindings)
            inner_params = tuple(substitute_type(p, bindings) for p in inner_params)
            outer_effects = function_effects(outer)
            inner_effects = function_effects(inner)
            if outer_effects is None or inner_effects is None:
                composed_effects = None
            else:
                composed_effects = tuple(sorted(set(outer_effects) | set(inner_effects)))
            return function_type((inner_params[0],), outer_result, composed_effects)
        if expr.name == 'apply':
            if len(expr.args) < 1:
                raise TypeError("function 'apply' expects a function and argument(s)")
            fn_type = infer(expr.args[0], env)
            if not is_function(fn_type):
                raise TypeError(f"apply expects a Function, got {fn_type}")
            params = function_params(fn_type)
            args = expr.args[1:]
            if len(params) != len(args):
                raise TypeError(f"apply expects {len(params)} argument(s) for the function, got {len(args)}")
            bindings = {}
            for index, (arg, expected) in enumerate(zip(args, params), 1):
                actual = infer(arg, env)
                if not generic_match(expected, actual, bindings):
                    raise _semantic_error(f"argument {index} of 'apply' expects {substitute_type(expected, bindings)}, got {actual}", 'E2004', function='apply', argument=index, expected_type=str(substitute_type(expected, bindings)), actual_type=str(actual))
            return substitute_type(function_result(fn_type), bindings)
        if expr.name not in sigs:
            local_type = env.names.get(expr.name)
            if local_type is not None and is_function(local_type):
                params = function_params(local_type)
                result = function_result(local_type)
            else:
                error = _semantic_error(f"unknown function '{expr.name}'", 'E2002', function=expr.name)
                # Keep the diagnostic code/message stable for editor integrations,
                # while offering a restrained spelling hint to beginners.
                candidates = set(sigs) | set(env.functions or {})
                candidates.update(
                    name for name, value in env.names.items()
                    if is_function(value)
                )
                candidates.discard(expr.name)
                matches = get_close_matches(expr.name, sorted(candidates), n=2, cutoff=0.78)
                if len(matches) == 1:
                    error.hint = (
                        f"did you mean '{matches[0]}'? Check the function name "
                        "and whether its module is imported."
                    )
                elif len(matches) > 1:
                    error.hint = (
                        "check the function name and imports; possible functions: "
                        + ", ".join(repr(name) for name in matches)
                    )
                raise error
        else:
            params, result = sigs[expr.name]
        if len(params) != len(expr.args):
            raise _semantic_error(f"function '{expr.name}' expects {len(params)} argument(s), got {len(expr.args)}", 'E2003', function=expr.name, expected_arity=len(params), actual_arity=len(expr.args))
        bindings = {}
        for index, (arg, expected) in enumerate(zip(expr.args, params), 1):
            actual = infer(arg, env)
            if not generic_match(expected, actual, bindings):
                raise _semantic_error(f"argument {index} of '{expr.name}' expects {substitute_type(expected, bindings)}, got {actual}", 'E2004', function=expr.name, argument=index, expected_type=str(substitute_type(expected, bindings)), actual_type=str(actual))
        return substitute_type(result, bindings)
    raise TypeError(f'unsupported expression node {type(expr).__name__}')


def infer(expr: Expr, env: TypeEnv) -> Type:
    span = source_span_of(expr)
    if span is None:
        return _infer_impl(expr, env)
    try:
        with source_location(span.start.line, span.start.column, span.end.column if span.end else None):
            return _infer_impl(expr, env)
    except TypeError as exc:
        # Preserve the expression location after the context manager restores
        # the caller's source location.  For an error produced directly by a
        # binary expression, also retain operand locations for richer IDE
        # diagnostics.
        if getattr(exc, "span", None) is None:
            exc.span = span
        if isinstance(expr, Binary) and getattr(exc, "span", None) == span and not getattr(exc, "related_spans", None):
            related = []
            left_span = source_span_of(expr.left)
            right_span = source_span_of(expr.right)
            if left_span is not None:
                related.append(DiagnosticRelatedSpan(left_span, "left operand"))
            if right_span is not None:
                related.append(DiagnosticRelatedSpan(right_span, "right operand"))
            if related:
                exc.related_spans = tuple(related)
                exc.hint = "use operands with compatible types for this operator"
            diagnostic_data = dict(getattr(exc, "diagnostic_data", {}) or {})
            diagnostic_data.setdefault("operator", expr.op)
            diagnostic_data.setdefault("left_type", str(infer(expr.left, env)))
            diagnostic_data.setdefault("right_type", str(infer(expr.right, env)))
            exc.diagnostic_data = diagnostic_data
        raise


def _infer_local_collection(statement, env: TypeEnv):
    source_type = env.names.get(statement.source)
    if source_type is None:
        raise TypeError(f"unknown collection '{statement.source}'")
    if source_type.name != "List":
        raise TypeError(f"collection '{statement.source}' has type {source_type}, expected List")
    item_type = source_type.args[0] if source_type.args else ANY
    current_type = source_type
    for operation, expression, initial, direction in statement.stages:
        local_names = dict(env.names)
        local_names.update({"item": item_type, "row": item_type})
        if operation == "where":
            result = infer(expression, TypeEnv(local_names, env.fields, env.properties, env.functions, env.record_params, env.function_effect_contracts, env.scope_prefix))
            if result != BOOLEAN and result != ANY:
                raise _semantic_error(f"where condition must be Boolean, got {result}", "E2006", expected_type=str(BOOLEAN), actual_type=str(result), construct="where")
        elif operation == "map":
            item_type = infer(expression, TypeEnv(local_names, env.fields, env.properties, env.functions, env.record_params, env.function_effect_contracts, env.scope_prefix))
            current_type = list_type(item_type)
        elif operation == "sort":
            infer(expression, TypeEnv(local_names, env.fields, env.properties, env.functions, env.record_params, env.function_effect_contracts, env.scope_prefix))
        elif operation == "reduce":
            initial_type = infer(initial, env)
            local_names["acc"] = initial_type
            step_type = infer(expression, TypeEnv(local_names, env.fields, env.properties, env.functions, env.record_params, env.function_effect_contracts, env.scope_prefix))
            if not unify_types(initial_type, step_type, {}):
                raise _semantic_error(f"reduce step returns {step_type}, expected {initial_type}", "E2000", construct="reduce")
            current_type = initial_type
        elif operation == "count":
            current_type = NUMBER
        elif operation in {"sum", "max", "min", "average", "avg"}:
            if expression is not None:
                item_type = infer(expression, TypeEnv(local_names, env.fields, env.properties, env.functions, env.record_params, env.function_effect_contracts, env.scope_prefix))
            current_type = item_type if operation in {"max", "min"} else NUMBER
        elif operation in {"any", "all"}:
            if expression is not None:
                value_type = infer(expression, TypeEnv(local_names, env.fields, env.properties, env.functions, env.record_params, env.function_effect_contracts, env.scope_prefix))
                if value_type not in {BOOLEAN, ANY}:
                    raise _semantic_error(f"{operation} expects Boolean values, got {value_type}", "E2006", construct=operation)
            current_type = BOOLEAN
    return current_type

def infer_block(body, env: TypeEnv):
    """Infer a sequential block; let-bindings extend the local environment."""
    result = None
    for stmt in body:
        if isinstance(stmt, FunctionDecl):
            result = _register_local_function(stmt, env)
        elif isinstance(stmt, LetOp):
            if stmt.name in env.names:
                raise _semantic_error(f"duplicate local variable '{stmt.name}'", "E2000", name=stmt.name, construct="duplicate_local_variable")
            typ = infer(stmt.expr, env)
            env.names[stmt.name] = typ
            result = typ
        elif isinstance(stmt, LocalCollectionOp):
            if stmt.name in env.names:
                raise _semantic_error(f"duplicate local variable '{stmt.name}'", "E2000", name=stmt.name, construct="duplicate_local_variable")
            result = _infer_local_collection(stmt, env)
            env.names[stmt.name] = result
        elif isinstance(stmt, ReturnOp):
            result = infer(stmt.expr, env)
            return result
        elif isinstance(stmt, IfOp):
            cond = infer(stmt.condition, env)
            if cond != BOOLEAN:
                raise _semantic_error(f"if condition must be Boolean, got {cond}", "E2006", expected_type=str(BOOLEAN), actual_type=str(cond), construct="if_statement")
            then_env = TypeEnv(dict(env.names), env.fields, env.properties, env.functions, env.record_params, env.function_effect_contracts, env.scope_prefix)
            else_env = TypeEnv(dict(env.names), env.fields, env.properties, env.functions, env.record_params, env.function_effect_contracts, env.scope_prefix)
            then_result = infer_block_partial(stmt.then_body, then_env)
            else_result = infer_block_partial(stmt.else_body, else_env) if stmt.else_body else None
            if then_result is not None and else_result is not None and not unify_types(then_result, else_result, {}):
                raise _semantic_error(f"if branches return incompatible types: {then_result} and {else_result}", expected_type=str(then_result), actual_type=str(else_result), construct="if_statement")
            if then_result is not None and else_result is not None:
                result = then_result
            else:
                result = None
        elif isinstance(stmt, Expr):
            result = infer(stmt, env)
        else:
            raise TypeError(f"unsupported statement node {type(stmt).__name__}")
    if result is not None:
        return result
    raise TypeError("function/property body requires a return statement")

def infer_block_partial(body, env: TypeEnv):
    """Infer a block that may fall through; used for if branches."""
    result = None
    for stmt in body:
        if isinstance(stmt, FunctionDecl):
            _register_local_function(stmt, env)
        elif isinstance(stmt, LetOp):
            if stmt.name in env.names:
                raise _semantic_error(f"duplicate local variable '{stmt.name}'", "E2000", name=stmt.name, construct="duplicate_local_variable")
            env.names[stmt.name] = infer(stmt.expr, env)
        elif isinstance(stmt, LocalCollectionOp):
            if stmt.name in env.names:
                raise _semantic_error(f"duplicate local variable '{stmt.name}'", "E2000", name=stmt.name, construct="duplicate_local_variable")
            env.names[stmt.name] = _infer_local_collection(stmt, env)
        elif isinstance(stmt, ReturnOp):
            result = infer(stmt.expr, env)
            return result
        elif isinstance(stmt, IfOp):
            cond = infer(stmt.condition, env)
            if cond != BOOLEAN:
                raise _semantic_error(f"if condition must be Boolean, got {cond}", "E2006", expected_type=str(BOOLEAN), actual_type=str(cond), construct="if_statement")
            tr = infer_block_partial(stmt.then_body, TypeEnv(dict(env.names), env.fields, env.properties, env.functions, env.record_params, env.function_effect_contracts, env.scope_prefix))
            er = infer_block_partial(stmt.else_body, TypeEnv(dict(env.names), env.fields, env.properties, env.functions, env.record_params, env.function_effect_contracts, env.scope_prefix)) if stmt.else_body else None
            if tr is not None and er is not None and not unify_types(tr, er, {}):
                raise _semantic_error(f"if branches return incompatible types: {tr} and {er}", expected_type=str(tr), actual_type=str(er), construct="if_statement")
            if tr is not None and er is not None:
                result = tr
        elif isinstance(stmt, Expr):
            infer(stmt, env)
        else:
            raise TypeError(f"unsupported statement node {type(stmt).__name__}")
    return result
