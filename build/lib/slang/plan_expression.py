"""Shared S-Lang expression evaluator for plan and reference runtimes.

The evaluator contains expression semantics only. Statement/block execution remains
in the respective runtime, while unsupported property/function paths may fall back
to the verified reference interpreter.
"""
from __future__ import annotations
import math
from .ast import *
from .stdlib_runtime import execute_registered_stdlib, execute_runtime_call
# Imported once, after ``core`` has been initialized. Keeping these at module
# scope avoids a Python import lookup on every recursive expression evaluation.
from .plan_runtime_support import (
    RecordValue, UserEntity, Body, Circle, FunctionValue, ComposedFunctionValue,
    Quantity, _is_function_value, _runtime_function_type, _resolve_io_path,
    type_name_for_value, domain_registry, function_params, function_result,
    function_type, get_stdlib_function, pow2, qadd, qsub, qmul, qdiv,
)


def eval_expr(expr, p, row=None, local=None):
    if isinstance(expr, Literal):
        if isinstance(expr.value, list):
            return [eval_expr(item, p, row, local) for item in expr.value]
        if isinstance(expr.value, dict):
            return RecordValue(None, {key: eval_expr(value, p, row, local) for key, value in expr.value.items()})
        return expr.value
    if isinstance(expr, Name):
        if local is not None and expr.name in local: return local[expr.name]
        if expr.name in getattr(p, "_states", {}): return p._states[expr.name]
        if row is not None and expr.name in ("row", "item"): return row
        if row is not None and isinstance(row, dict) and expr.name in row: return row[expr.name]
        for b in p.bodies:
            if b.name==expr.name: return b
        for c in (p.circles or []):
            if c.name==expr.name: return c
        if expr.name in getattr(p, '_collections', {}): return p._collections[expr.name]
        if expr.name in getattr(p, '_bindings', {}): return p._bindings[expr.name]
        planned_functions = getattr(p, "_plan_functions", {})
        if expr.name in planned_functions:
            return planned_functions[expr.name]
        for fn in p.ast.functions:
            if fn.name == expr.name:
                return FunctionValue(fn, p, closure=getattr(p, "_bindings", {}))
        if expr.name in (p.entities or {}): return p.entities[expr.name]
        if expr.name==getattr(p,'_data_result_name',None): return getattr(p,'_data_result',[])
        raise TypeError(f"unknown value '{expr.name}'")
    if isinstance(expr, Property):
        base=eval_expr(expr.base,p,row,local)
        plan_properties = getattr(p, "_plan_properties", {})
        planned = plan_properties.get((type_name_for_value(base), expr.name))
        if planned is not None:
            return planned(base)
        for prop in p.ast.properties:
            if prop.entity_type == type_name_for_value(base) and prop.name == expr.name:
                raise TypeError(f"unplanned property '{expr.name}' requires reference runtime")
        if isinstance(base, UserEntity):
            if expr.name not in base.fields: raise TypeError(f"unknown property '{expr.name}' on {base.type_name}")
            return base.fields[expr.name]
        if isinstance(base, Body):
            if expr.name not in base.fields: raise TypeError(f"unknown property '{expr.name}' on Body")
            return base.fields[expr.name]
        entity_name = type_name_for_value(base)
        if (entity_name, expr.name) in domain_registry().property_evaluators:
            return domain_registry().evaluate_property(entity_name, expr.name, base)
        if isinstance(base,dict):
            if expr.name not in base: raise TypeError(f"unknown field '{expr.name}'")
            return base[expr.name]
        raise TypeError(f"unknown property '{expr.name}'")
    if isinstance(expr, Field):
        if isinstance(expr.base, Name) and expr.base.name == "row" and row is not None:
            if expr.name not in row: raise TypeError(f"unknown field '{expr.name}'")
            return row[expr.name]
        return eval_expr(Property(expr.base,expr.name),p,row)
    if isinstance(expr, Binary):
        a,b=eval_expr(expr.left,p,row,local),eval_expr(expr.right,p,row,local)
        if expr.op=='+': return qadd(a,b) if isinstance(a,Quantity) else a+b
        if expr.op=='-': return qsub(a,b) if isinstance(a,Quantity) else a-b
        if expr.op=='*': return qmul(a,b)
        if expr.op=='/': return qdiv(a,b)
        if expr.op=='%':
            if b == 0: raise ZeroDivisionError('modulo by zero')
            if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
                raise TypeError('operator % requires numeric operands')
            return math.fmod(a, b)
        if expr.op=='^': return pow2(a) if isinstance(a,Quantity) and b==2 else a**b
    if isinstance(expr, Conditional):
        condition = eval_expr(expr.condition, p, row, local)
        if not isinstance(condition, bool):
            raise TypeError(f'conditional condition must be Boolean, got {type(condition).__name__}')
        return eval_expr(expr.then_expr if condition else expr.else_expr, p, row, local)
    if isinstance(expr, Compare):
        a,b=eval_expr(expr.left,p,row,local),eval_expr(expr.right,p,row,local)
        return {'>=':a>=b,'<=':a<=b,'==':a==b,'!=':a!=b,'>':a>b,'<':a<b}[expr.op]
    if isinstance(expr, Logical):
        left = eval_expr(expr.left, p, row, local)
        if not isinstance(left, bool): raise TypeError(f"logical operand must be Boolean, got {type(left).__name__}")
        if expr.op == 'not': return not left
        if expr.op == 'and':
            if not left: return False
            right = eval_expr(expr.right, p, row, local)
            if not isinstance(right, bool): raise TypeError(f"logical operand must be Boolean, got {type(right).__name__}")
            return right
        if expr.op == 'or':
            if left: return True
            right = eval_expr(expr.right, p, row, local)
            if not isinstance(right, bool): raise TypeError(f"logical operand must be Boolean, got {type(right).__name__}")
            return right
        raise TypeError(f"unknown logical operator '{expr.op}'")
    if isinstance(expr, Call):
        # A first-class function stored in a local or top-level binding can be
        # invoked directly: `let f = double; f(5)`. Named declarations remain
        # available through the same call syntax.
        bound_callable = None
        if local is not None and expr.name in local:
            bound_callable = local[expr.name]
        elif expr.name in getattr(p, '_bindings', {}):
            bound_callable = p._bindings[expr.name]
        if _is_function_value(bound_callable):
            args=[eval_expr(x,p,row,local) for x in expr.args]
            return bound_callable(args)
        args=[eval_expr(x,p,row,local) for x in expr.args]
        planned_functions = getattr(p, "_plan_functions", {})
        if expr.name in planned_functions:
            return planned_functions[expr.name](args)
        handled, result = execute_registered_stdlib(expr.name, args)
        if handled:
            return result
        if expr.name == 'apply':
            if len(args) < 1 or not _is_function_value(args[0]):
                raise TypeError('apply expects a Function and argument(s)')
            return args[0](args[1:])
        if expr.name == 'compose':
            if len(args) != 2 or not _is_function_value(args[0]) or not _is_function_value(args[1]):
                raise TypeError('compose expects two Function values')
            if len(function_params(_runtime_function_type(args[0]))) != 1 or len(function_params(_runtime_function_type(args[1]))) != 1:
                raise TypeError('compose currently requires unary functions')
            return ComposedFunctionValue(args[0], args[1])
        if expr.name == 'len':
            if len(args) != 1 or not isinstance(args[0], (str, list, tuple, dict)): raise TypeError('len expects a Text, List, Tuple, or Map')
            return len(args[0])
        if expr.name == 'contains':
            if len(args) != 2 or not isinstance(args[0], (str, list, tuple, dict)): raise TypeError('contains expects a Text, List, Tuple, or Map as first argument')
            return args[1] in args[0]
        if expr.name == 'join':
            if len(args) != 2 or not isinstance(args[0], list) or not isinstance(args[1], str): raise TypeError('join expects List<Text> and a Text separator')
            if not all(isinstance(x, str) for x in args[0]): raise TypeError('join expects List<Text>')
            return args[1].join(args[0])
        if expr.name == 'first':
            if len(args) != 1 or not isinstance(args[0], list): raise TypeError('first expects List<T>')
            if not args[0]: raise RuntimeError('first cannot operate on an empty List')
            return args[0][0]
        if expr.name == 'last':
            if len(args) != 1 or not isinstance(args[0], list): raise TypeError('last expects List<T>')
            if not args[0]: raise RuntimeError('last cannot operate on an empty List')
            return args[0][-1]
        if expr.name == 'append':
            if len(args) != 2 or not isinstance(args[0], list): raise TypeError('append expects List<T> and T')
            result = list(args[0])
            result.append(args[1])
            return result
        if expr.name == 'flatten':
            if len(args) != 1 or not isinstance(args[0], list): raise TypeError('flatten expects List<List<T>>')
            result = []
            for part in args[0]:
                if not isinstance(part, list): raise TypeError('flatten expects List<List<T>>')
                result.extend(part)
            return result
        if expr.name == 'distinct':
            if len(args) != 1 or not isinstance(args[0], list): raise TypeError('distinct expects List<T>')
            result = []
            for value in args[0]:
                if not any(value == seen for seen in result):
                    result.append(value)
            return result
        if expr.name == 'range_numbers':
            if len(args) not in (2, 3) or not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in args):
                raise TypeError('range_numbers expects Number, Number, optional Number')
            from .stdlib.collections import range_numbers
            return range_numbers(*args)
        if expr.name == 'reverse':
            if len(args) != 1 or not isinstance(args[0], list): raise TypeError('reverse expects List<T>')
            from .stdlib.collections import reverse
            return reverse(args[0])
        if expr.name == 'sort_numbers':
            if len(args) != 1 or not isinstance(args[0], list): raise TypeError('sort_numbers expects List<Number>')
            from .stdlib.collections import sort_numbers
            return sort_numbers(args[0])
        if expr.name == 'sum_numbers':
            if len(args) != 1 or not isinstance(args[0], list): raise TypeError('sum_numbers expects List<Number>')
            from .stdlib.collections import sum_numbers
            return sum_numbers(args[0])
        if expr.name in ('min_number', 'max_number'):
            if len(args) != 1 or not isinstance(args[0], list): raise TypeError(f'{expr.name} expects List<Number>')
            from .stdlib.collections import min_number, max_number
            return {'min_number': min_number, 'max_number': max_number}[expr.name](args[0])
        if expr.name == 'count_value':
            if len(args) != 2 or not isinstance(args[0], list): raise TypeError('count_value expects List<T> and T')
            from .stdlib.collections import count_value
            return count_value(args[0], args[1])
        if expr.name in ('any_true', 'all_true'):
            if len(args) != 1 or not isinstance(args[0], list): raise TypeError(f'{expr.name} expects List<Boolean>')
            from .stdlib.collections import any_true, all_true
            return {'any_true': any_true, 'all_true': all_true}[expr.name](args[0])
        if expr.name in ('chunk', 'pairwise'):
            from .stdlib.collections import chunk, pairwise
            if expr.name == 'chunk':
                if len(args) != 2 or not isinstance(args[0], list): raise TypeError('chunk expects List<T> and Number')
                return chunk(args[0], args[1])
            if len(args) != 1 or not isinstance(args[0], list): raise TypeError('pairwise expects List<T>')
            return pairwise(args[0])
        if expr.name in ('take', 'skip'):
            if len(args) != 2 or not isinstance(args[0], list) or not isinstance(args[1], (int, float)) or isinstance(args[1], bool):
                raise TypeError(f'{expr.name} expects List<T> and Number')
            count = int(args[1])
            if count < 0: raise ValueError(f'{expr.name} count cannot be negative')
            return args[0][:count] if expr.name == 'take' else args[0][count:]
            # Catalog-backed IO uses the same runtime permission/trace/limit boundary
        # as registered stdlib calls. Path arguments are resolved against the
        # current execution context before the actual stdlib function is invoked.
        from .stdlib.catalog import IO_LIBRARY
        if expr.name in IO_LIBRARY:
            import importlib
            def _catalog_io(values):
                module_name, _effect, _description, _capability = IO_LIBRARY[expr.name]
                module = importlib.import_module(module_name)
                fn = getattr(module, expr.name)
                resolved = list(values)
                if expr.name in {
                    'read', 'write', 'exists', 'read_csv', 'write_csv', 'read_json', 'write_json',
                    'file_size', 'is_file', 'is_directory', 'list_directory',
                    'list_files', 'list_directories', 'make_directory',
                    'remove_directory', 'remove_directory_tree', 'read_text',
                    'write_text', 'append_text', 'read_lines', 'write_lines',
                    'remove_file', 'make_directories'
                }:
                    if not resolved or not isinstance(resolved[0], str):
                        raise TypeError(f'{expr.name} expects a Text path')
                    resolved[0] = str(_resolve_io_path(p, resolved[0]))
                elif expr.name in {'copy_file', 'move_file'}:
                    if len(resolved) != 2 or not all(isinstance(v, str) for v in resolved):
                        raise TypeError(f'{expr.name} expects two Text paths')
                    resolved[0] = str(_resolve_io_path(p, resolved[0]))
                    resolved[1] = str(_resolve_io_path(p, resolved[1]))
                result = fn(*resolved)
                if expr.name == 'read_csv':
                    return [RecordValue(None, row) for row in result]
                return result
            handled, result = execute_runtime_call(expr.name, args, _catalog_io)
            if handled:
                return result
    
        if expr.name == 'read':
            if len(args) != 1 or not isinstance(args[0], str): raise TypeError('read expects a Text path')
            from pathlib import Path
            try:
                return _resolve_io_path(p, args[0]).read_text(encoding='utf-8')
            except OSError as exc:
                raise RuntimeError(f"read failed for '{args[0]}': {exc}") from exc
        if expr.name == 'write':
            if len(args) != 2 or not isinstance(args[0], str) or not isinstance(args[1], str):
                raise TypeError('write expects a Text path and Text content')
            from pathlib import Path
            try:
                _resolve_io_path(p, args[0]).write_text(args[1], encoding='utf-8')
            except OSError as exc:
                raise RuntimeError(f"write failed for '{args[0]}': {exc}") from exc
            return True
        if expr.name == 'read_lines':
            if len(args) != 1 or not isinstance(args[0], str): raise TypeError('read_lines expects a Text path')
            from pathlib import Path
            try:
                return _resolve_io_path(p, args[0]).read_text(encoding='utf-8').splitlines()
            except OSError as exc:
                raise RuntimeError(f"read_lines failed for '{args[0]}': {exc}") from exc
        if expr.name == 'now_utc':
            if args:
                raise TypeError('now_utc expects no arguments')
            from slang.stdlib.datetime import now_utc
            return now_utc()
        if expr.name == 'today_utc':
            if args:
                raise TypeError('today_utc expects no arguments')
            from slang.stdlib.datetime import today_utc
            return today_utc()
        if expr.name in ('parse_datetime', 'format_datetime', 'add_seconds_datetime', 'diff_seconds_datetime', 'add_days_datetime', 'add_months_datetime', 'start_of_day_datetime', 'end_of_day_datetime', 'date_components_datetime', 'is_leap_year', 'days_in_month', 'weekday_datetime', 'week_number_datetime'):
            from slang.stdlib import datetime as _datetime_stdlib
            fn = getattr(_datetime_stdlib, expr.name)
            try:
                return fn(*args)
            except (TypeError, ValueError) as exc:
                raise RuntimeError(f'{expr.name} failed: {exc}') from exc
        if expr.name == 'read_json':
            if len(args) != 1 or not isinstance(args[0], str): raise TypeError('read_json expects a Text path')
            import json
            try:
                return json.loads(_resolve_io_path(p, args[0]).read_text(encoding='utf-8'))
            except (OSError, ValueError) as exc:
                raise RuntimeError(f"read_json failed for '{args[0]}': {exc}") from exc
        if expr.name == 'write_json':
            if len(args) != 2 or not isinstance(args[0], str): raise TypeError('write_json expects a Text path and value')
            import json
            try:
                _resolve_io_path(p, args[0]).write_text(json.dumps(args[1], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding='utf-8')
            except (OSError, TypeError, ValueError) as exc:
                raise RuntimeError(f"write_json failed for '{args[0]}': {exc}") from exc
            return True
        if expr.name == 'arguments':
            if args: raise TypeError('arguments expects no arguments')
            import sys
            handled, result = execute_runtime_call(expr.name, args, lambda values: list(sys.argv[1:]), expected_args=0)
            return result if handled else None
        if expr.name == 'environment':
            if len(args) != 1 or not isinstance(args[0], str): raise TypeError('environment expects a Text name')
            import os
            handled, result = execute_runtime_call(expr.name, args, lambda values: os.environ.get(values[0], ''), expected_args=1)
            return result if handled else None
        if expr.name in ('current_directory', 'platform_name', 'process_id', 'sleep_seconds', 'home_directory', 'temp_directory', 'executable_path', 'command_exists'):
            from slang.stdlib import process as _process_stdlib
            handled, result = execute_runtime_call(expr.name, args, lambda values: getattr(_process_stdlib, expr.name)(*values))
            return result if handled else None
        if expr.name == 'write_lines':
            if len(args) != 2 or not isinstance(args[0], str) or not isinstance(args[1], list):
                raise TypeError('write_lines expects a Text path and List<Text>')
            if not all(isinstance(x, str) for x in args[1]): raise TypeError('write_lines expects List<Text>')
            from pathlib import Path
            try:
                _resolve_io_path(p, args[0]).write_text('\n'.join(args[1]) + ('\n' if args[1] else ''), encoding='utf-8')
            except OSError as exc:
                raise RuntimeError(f"write_lines failed for '{args[0]}': {exc}") from exc
            return True
        if expr.name == 'exists':
            if len(args) != 1 or not isinstance(args[0], str): raise TypeError('exists expects a Text path')
            from pathlib import Path
            return _resolve_io_path(p, args[0]).exists()
        if expr.name == 'file_size':
            if len(args) != 1 or not isinstance(args[0], str): raise TypeError('file_size expects a Text path')
            from .stdlib.files import file_size
            try:
                return file_size(str(_resolve_io_path(p, args[0])))
            except OSError as exc:
                raise RuntimeError(f"file_size failed for '{args[0]}': {exc}") from exc
        if expr.name == 'is_file':
            if len(args) != 1 or not isinstance(args[0], str): raise TypeError('is_file expects a Text path')
            from .stdlib.files import is_file
            return is_file(str(_resolve_io_path(p, args[0])))
        if expr.name == 'is_directory':
            if len(args) != 1 or not isinstance(args[0], str): raise TypeError('is_directory expects a Text path')
            from .stdlib.files import is_directory
            return is_directory(str(_resolve_io_path(p, args[0])))
        if expr.name == 'list_directory':
            if len(args) != 1 or not isinstance(args[0], str): raise TypeError('list_directory expects a Text path')
            from .stdlib.files import list_directory
            try:
                return list_directory(str(_resolve_io_path(p, args[0])))
            except OSError as exc:
                raise RuntimeError(f"list_directory failed for '{args[0]}': {exc}") from exc
        if expr.name in ('list_files', 'list_directories'):
            if len(args) != 1 or not isinstance(args[0], str): raise TypeError(f'{expr.name} expects a Text path')
            from .stdlib.files import list_directories, list_files
            try:
                func = list_files if expr.name == 'list_files' else list_directories
                return func(str(_resolve_io_path(p, args[0])))
            except OSError as exc:
                raise RuntimeError(f"{expr.name} failed for '{args[0]}': {exc}") from exc
        if expr.name == 'remove_directory_tree':
            if len(args) != 1 or not isinstance(args[0], str): raise TypeError('remove_directory_tree expects a Text path')
            from .stdlib.files import remove_directory_tree
            try:
                return remove_directory_tree(str(_resolve_io_path(p, args[0])))
            except OSError as exc:
                raise RuntimeError(f"remove_directory_tree failed for '{args[0]}': {exc}") from exc
        if expr.name == 'make_directory':
            if len(args) != 1 or not isinstance(args[0], str): raise TypeError('make_directory expects a Text path')
            from .stdlib.files import make_directory
            try:
                return make_directory(str(_resolve_io_path(p, args[0])))
            except OSError as exc:
                raise RuntimeError(f"make_directory failed for '{args[0]}': {exc}") from exc
        if expr.name == 'remove_directory':
            if len(args) != 1 or not isinstance(args[0], str): raise TypeError('remove_directory expects a Text path')
            from .stdlib.files import remove_directory
            try:
                return remove_directory(str(_resolve_io_path(p, args[0])))
            except OSError as exc:
                raise RuntimeError(f"remove_directory failed for '{args[0]}': {exc}") from exc
        if expr.name in ('remove_file', 'copy_file', 'move_file', 'make_directories'):
            expected = {
                'remove_file': 1, 'make_directories': 1,
                'copy_file': 2, 'move_file': 2,
            }[expr.name]
            if len(args) != expected or not all(isinstance(x, str) for x in args):
                raise TypeError(f'{expr.name} expects Text path arguments')
            from .stdlib.files import copy_file, make_directories, move_file, remove_file
            funcs = {'remove_file': remove_file, 'copy_file': copy_file, 'move_file': move_file, 'make_directories': make_directories}
            resolved = [_resolve_io_path(p, x) for x in args]
            try:
                return funcs[expr.name](*[str(x) for x in resolved])
            except OSError as exc:
                raise RuntimeError(f"{expr.name} failed: {exc}") from exc
        if expr.name == 'basename':
            if len(args) != 1 or not isinstance(args[0], str): raise TypeError('basename expects a Text path')
            from .stdlib.path import basename
            return basename(args[0])
        if expr.name == 'dirname':
            if len(args) != 1 or not isinstance(args[0], str): raise TypeError('dirname expects a Text path')
            from .stdlib.path import dirname
            return dirname(args[0])
        if expr.name == 'extension':
            if len(args) != 1 or not isinstance(args[0], str): raise TypeError('extension expects a Text path')
            from .stdlib.path import extension
            return extension(args[0])
        if expr.name == 'join_path':
            if len(args) != 2 or not all(isinstance(x, str) for x in args): raise TypeError('join_path expects two Text paths')
            from .stdlib.path import join_path
            return join_path(*args)
        if expr.name == 'normalize_path':
            if len(args) != 1 or not isinstance(args[0], str): raise TypeError('normalize_path expects a Text path')
            from .stdlib.path import normalize_path
            return normalize_path(args[0])
        if expr.name == 'read_csv':
            if len(args) != 1 or not isinstance(args[0], str): raise TypeError('read_csv expects a Text path')
            from .stdlib.csv import read_csv
            try:
                return [RecordValue(None, row) for row in read_csv(str(_resolve_io_path(p, args[0])))]
            except (OSError, ValueError) as exc:
                raise RuntimeError(f"read_csv failed for '{args[0]}': {exc}") from exc
        if expr.name == 'write_csv':
            if len(args) != 2 or not isinstance(args[0], str) or not isinstance(args[1], list):
                raise TypeError('write_csv expects a Text path and List')
            if not all(isinstance(x, dict) for x in args[1]):
                raise TypeError('write_csv expects a List<Record>')
            from .stdlib.csv import write_csv
            try:
                write_csv(str(_resolve_io_path(p, args[0])), args[1])
            except OSError as exc:
                raise RuntimeError(f"write_csv failed for '{args[0]}': {exc}") from exc
            return True
        if expr.name == 'csv_headers':
            if len(args) != 1 or not isinstance(args[0], list): raise TypeError('csv_headers expects a List')
            from .stdlib.csv import csv_headers
            return csv_headers(args[0])
        if expr.name == 'keys':
            if len(args) != 1 or not isinstance(args[0], dict): raise TypeError('keys expects a Record')
            return list(args[0].keys())
        if expr.name == 'get':
            if len(args) != 2 or not isinstance(args[0], dict) or not isinstance(args[1], str): raise TypeError('get expects a Record and Text key')
            return args[0].get(args[1])
        if expr.name == 'has':
            if len(args) != 2 or not isinstance(args[0], dict) or not isinstance(args[1], str): raise TypeError('has expects a Record and Text key')
            return args[1] in args[0]
        if expr.name == 'abs_number':
            if len(args) != 1 or not isinstance(args[0], (int, float)) or isinstance(args[0], bool): raise TypeError('abs_number expects Number')
            from .stdlib.math import abs_number
            return abs_number(args[0])
        if expr.name == 'sqrt':
            if len(args) != 1 or not isinstance(args[0], (int, float)) or isinstance(args[0], bool): raise TypeError('sqrt expects Number')
            from .stdlib.math import sqrt
            return sqrt(args[0])
        if expr.name in ('floor', 'ceil', 'round_number'):
            if len(args) != 1 or not isinstance(args[0], (int, float)) or isinstance(args[0], bool): raise TypeError(f'{expr.name} expects Number')
            from .stdlib.math import floor, ceil, round_number
            return {'floor': floor, 'ceil': ceil, 'round_number': round_number}[expr.name](args[0])
        if expr.name in ('trim', 'lower', 'upper'):
            if len(args) != 1 or not isinstance(args[0], str): raise TypeError(f'{expr.name} expects Text')
            from .stdlib.text import trim, lower, upper
            return {'trim': trim, 'lower': lower, 'upper': upper}[expr.name](args[0])
        if expr.name in ('starts_with', 'ends_with'):
            if len(args) != 2 or not all(isinstance(x, str) for x in args): raise TypeError(f'{expr.name} expects Text, Text')
            from .stdlib.text import starts_with, ends_with
            return {'starts_with': starts_with, 'ends_with': ends_with}[expr.name](args[0], args[1])
        if expr.name == 'replace':
            if len(args) != 3 or not all(isinstance(x, str) for x in args): raise TypeError('replace expects Text, Text, Text')
            from .stdlib.text import replace
            return replace(args[0], args[1], args[2])
        if expr.name == 'split':
            if len(args) != 2 or not all(isinstance(x, str) for x in args): raise TypeError('split expects Text, Text')
            from .stdlib.text import split
            return split(args[0], args[1])
        if expr.name == 'json_parse':
            if len(args) != 1 or not isinstance(args[0], str): raise TypeError('json_parse expects Text')
            from .stdlib.json import parse
            try:
                return parse(args[0])
            except ValueError as exc:
                raise RuntimeError(
                    f"json_parse could not read valid JSON: {exc}. Check quotes, commas, brackets, and the value at the reported position."
                ) from exc
        if expr.name in ('json_stringify', 'json_pretty'):
            if len(args) != 1: raise TypeError(f'{expr.name} expects one value')
            from .stdlib.json import pretty, stringify
            try:
                return (pretty if expr.name == 'json_pretty' else stringify)(args[0])
            except Exception as exc:
                raise RuntimeError(f'{expr.name} failed: {exc}') from exc
        if expr.name in ('json_get', 'json_has', 'json_set'):
            from .stdlib.json import get_path, has_path, set_path
            try:
                if expr.name == 'json_get':
                    if len(args) != 3 or not isinstance(args[1], str): raise TypeError('json_get expects value, Text path, default')
                    return get_path(args[0], args[1], args[2])
                if expr.name == 'json_has':
                    if len(args) != 2 or not isinstance(args[1], str): raise TypeError('json_has expects value, Text path')
                    return has_path(args[0], args[1])
                if len(args) != 3 or not isinstance(args[1], str): raise TypeError('json_set expects value, Text path, replacement')
                return set_path(args[0], args[1], args[2])
            except Exception as exc:
                raise RuntimeError(f'{expr.name} failed: {exc}') from exc
        if expr.name == 'to_number':
            if len(args) != 1 or not isinstance(args[0], str): raise TypeError('to_number expects Text')
            try:
                value=float(args[0].strip())
            except ValueError as exc:
                raise RuntimeError(
                    f"to_number cannot convert {args[0]!r} to Number. Provide numeric text such as '12' or '3.5'; check for letters or a decimal separator such as a comma."
                ) from exc
            return int(value) if value.is_integer() else value
        for decl in p.ast.entities:
            if expr.name == decl.name:
                values = args
                if len(values) != len(decl.fields): raise TypeError(f"entity '{decl.name}' expects {len(decl.fields)} argument(s), got {len(values)}")
                return UserEntity(decl.name, f"{decl.name}_value", {name: value for (name, _), value in zip(decl.fields, values)})
        for decl in p.ast.records:
            if expr.name == decl.name:
                if len(args) != len(decl.fields): raise TypeError(f"record '{decl.name}' expects {len(decl.fields)} argument(s), got {len(args)}")
                return RecordValue(decl.name, {name: value for (name, _), value in zip(decl.fields, args)})
        domain_fn = domain_registry().function(expr.name)
        if domain_fn is not None:
            return domain_fn.evaluator(args)
        for fn in p.ast.functions:
            if fn.name == expr.name:
                if len(args) != len(fn.parameters): raise TypeError(f"function '{fn.name}' expects {len(fn.parameters)} argument(s), got {len(args)}")
                fn_local = {name:value for (name,_),value in zip(fn.parameters,args)}
                raise TypeError(f"unplanned function '{expr.name}' requires reference runtime")
        raise TypeError(f"unknown function '{expr.name}'")
    raise TypeError(f"unsupported expression {type(expr).__name__}")


def eval_pipeline_expr(expr, p, row):
    # Keep the planned runtime on the same optimized scalar hot path as the
    # reference runtime. Unsupported expressions retain the full evaluator.
    value = _eval_pipeline_fast(expr, p, row)
    if value is not _PIPELINE_FAST_MISS:
        return value
    value = eval_expr(expr, p, row)
    from .plan_runtime_support import FunctionValue
    if isinstance(value, FunctionValue):
        return value([row])
    return value


_PIPELINE_FAST_MISS = object()

def _eval_pipeline_fast(expr, p, row):
    if isinstance(expr, Name):
        if expr.name in ("row", "item"):
            return row
        return _PIPELINE_FAST_MISS
    if isinstance(expr, Field):
        if isinstance(expr.base, Name) and expr.base.name in ("row", "item") and isinstance(row, dict):
            if expr.name not in row: raise TypeError(f"unknown field '{expr.name}'")
            return row[expr.name]
        return _PIPELINE_FAST_MISS
    if isinstance(expr, Property):
        if isinstance(expr.base, Name) and expr.base.name in ("row", "item") and isinstance(row, dict):
            if expr.name not in row: raise TypeError(f"unknown field '{expr.name}'")
            return row[expr.name]
        return _PIPELINE_FAST_MISS
    if isinstance(expr, Literal): return expr.value
    if isinstance(expr, Binary) and expr.op in {"+", "-", "*", "/", "^", "%"}:
        a=_eval_pipeline_fast(expr.left,p,row); b=_eval_pipeline_fast(expr.right,p,row)
        if a is _PIPELINE_FAST_MISS or b is _PIPELINE_FAST_MISS: return _PIPELINE_FAST_MISS
        return {"+":lambda:a+b,"-":lambda:a-b,"*":lambda:a*b,"/":lambda:a/b,"^":lambda:a**b,"%":lambda:math.fmod(a,b)}[expr.op]()
    if isinstance(expr, Compare):
        a=_eval_pipeline_fast(expr.left,p,row); b=_eval_pipeline_fast(expr.right,p,row)
        if a is _PIPELINE_FAST_MISS or b is _PIPELINE_FAST_MISS: return _PIPELINE_FAST_MISS
        return {">=":a>=b,"<=":a<=b,"==":a==b,"!=":a!=b,">":a>b,"<":a<b}[expr.op]
    if isinstance(expr, Logical):
        a=_eval_pipeline_fast(expr.left,p,row)
        if a is _PIPELINE_FAST_MISS: return _PIPELINE_FAST_MISS
        if expr.op=="not": return not a
        if expr.op=="and":
            if not a: return False
            b=_eval_pipeline_fast(expr.right,p,row); return _PIPELINE_FAST_MISS if b is _PIPELINE_FAST_MISS else bool(b)
        if expr.op=="or":
            if a: return True
            b=_eval_pipeline_fast(expr.right,p,row); return _PIPELINE_FAST_MISS if b is _PIPELINE_FAST_MISS else bool(b)
    if isinstance(expr, Conditional):
        c=_eval_pipeline_fast(expr.condition,p,row)
        if c is _PIPELINE_FAST_MISS: return _PIPELINE_FAST_MISS
        return _eval_pipeline_fast(expr.then_expr if c else expr.else_expr,p,row)
    if isinstance(expr, Call) and expr.name=="to_number" and len(expr.args)==1:
        value=_eval_pipeline_fast(expr.args[0],p,row)
        if value is _PIPELINE_FAST_MISS: return _PIPELINE_FAST_MISS
        if not isinstance(value,str): raise TypeError("to_number expects Text")
        try: number=float(value.strip())
        except ValueError as exc: raise RuntimeError(f"to_number cannot convert {value!r} to Number. Provide numeric text such as '12' or '3.5'; check for letters or a decimal separator such as a comma.") from exc
        return int(number) if number.is_integer() else number
    return _PIPELINE_FAST_MISS
