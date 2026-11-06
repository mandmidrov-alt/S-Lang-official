from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Any
from .ast import Name, Field, Binary, Compare, Logical, Call, Property, Literal, LetOp, ReturnOp, IfOp
from .memory_regions import MemoryRegion, parse_regions
@dataclass(frozen=True)
class DataShape:
    """Compile-time structural facts used by the cost model."""
    lower: int | None = None
    upper: int | None = None
    exact: bool = False
    numeric_ranges: tuple[tuple[str, float, float], ...] = ()
    complexity: str = "linear"
    reason: str = "not statically known"

    @property
    def cardinality(self):
        return self.lower if self.exact and self.lower == self.upper else None


@dataclass(frozen=True)
class ExecutionNode:
    binding:str
    kind:str
    result:str|None
    dependencies:tuple[str,...]
    external_sources:tuple[str,...]
    pure:bool
    definition:bool=False
    deterministic:bool=True
    access:str="read-only"
    order_sensitive:bool=False
    effects:tuple[str,...]=()
    memory_reads:tuple[str,...]=()
    memory_writes:tuple[str,...]=()
    memory_regions:tuple[str,...]=()
    memory_region_specs:tuple[MemoryRegion,...]=()
    cardinality:int|None=None
    cardinality_confidence:str="unknown"
    cardinality_reason:str="not statically known"
    data_shape:DataShape|None=None
    optimization_hints:tuple[str,...]=()
    # Semantic collection types resolved by the type checker.
    input_type:str|None=None
    output_type:str|None=None
    # Fully resolved structural schema. Unlike the display type strings above,
    # this carries concrete record field names/types across the pipeline.
    input_schema:object|None=None
    output_schema:object|None=None
    # Per-output-field provenance for record-producing transforms. Each entry is
    # (output_field, source_fields, certainty). This is a planning fact, not a
    # runtime dependency contract.
    record_field_provenance:tuple[tuple[str, tuple[str, ...], str], ...]=()

    @property
    def state_access(self)->str:
        if self.memory_reads and self.memory_writes: return "read-write"
        if self.memory_writes: return "write"
        if self.memory_reads: return "read"
        return "none"

    @property
    def reorderable(self)->bool:
        return self.deterministic and self.access == "read-only" and not self.order_sensitive and (not self.effects or self.effects == ("state-read",))

    @property
    def parallel_safe(self)->bool:
        return self.reorderable

    @property
    def effect_free(self)->bool:
        return not self.effects
@dataclass(frozen=True)
class ExecutionIR:
    nodes:tuple[ExecutionNode,...]
    def by_binding(self): return {n.binding:n for n in self.nodes}
    def type_contract(self):
        """Return the resolved node-type contract for backend lowering."""
        return tuple((n.binding, n.input_type, n.output_type) for n in self.nodes)

    def schema_contract(self):
        """Return concrete structural schemas without consulting the AST."""
        return tuple((n.binding, n.input_schema, n.output_schema) for n in self.nodes)
    def topological_order(self):
        # Dependencies may reference external semantic contracts such as
        # @fn:name and @prop:type.name. They are not ExecutionIR nodes and
        # therefore must not block the graph's topological ordering.
        bindings = {n.binding for n in self.nodes}
        rem={n.binding:{dep for dep in n.dependencies if dep in bindings} for n in self.nodes}; out=[]
        while rem:
            ready=sorted(k for k,v in rem.items() if not v)
            if not ready: raise ValueError('execution IR contains a dependency cycle')
            for k in ready: out.append(k); del rem[k]
            for v in rem.values(): v.difference_update(ready)
        return tuple(out)
def _type_text(value):
    if value is None:
        return None
    if getattr(value, "name", None) == "List" and getattr(value, "args", ()):
        return f"List<{_type_text(value.args[0])}>"
    if getattr(value, "name", None) == "Record" and getattr(value, "args", ()):
        return f"Record<{_type_text(value.args[0])}>"
    if getattr(value, "name", None) == "Function":
        return str(value)
    return getattr(value, "name", None) or str(value)

def _names(e:Any)->set[str]:
    if e is None:return set()
    if isinstance(e,Name):return {e.name}
    if isinstance(e,Literal):
        if isinstance(e.value, list):
            out=set()
            for item in e.value:
                out |= _names(item)
            return out
        if isinstance(e.value, dict):
            out=set()
            for item in e.value.values():
                out |= _names(item)
            return out
        return set()
    if isinstance(e,(Field,Property)):return _names(e.base)
    if isinstance(e,(Binary,Compare)):return _names(e.left)|_names(e.right)
    if isinstance(e,Logical):return _names(e.left)|(_names(e.right) if e.right is not None else set())
    if isinstance(e,Call):
        out={'@fn:'+e.name}
        for a in e.args:out|=_names(a)
        return out
    return set()
def _body_names(body):
    out=set(); locals=set()
    for op in body:
        if isinstance(op,LetOp):
            out|=_names(op.expr); locals.add(op.name)
        elif isinstance(op,ReturnOp): out|=_names(op.expr)
        elif isinstance(op,IfOp): out|=_names(op.condition)|_body_names(op.then_body)|_body_names(op.else_body)
    return out-locals
def _collection_regions(expr:Any, source:str|None)->set[str]:
    """Return conservative element-level regions touched by a collection expression.

    `row.field` becomes `source[*].field`; bare `row` becomes `source[*]`.
    The representation is intentionally symbolic: it is a dependency-analysis
    location, not a runtime address.
    """
    if not source:
        return set()
    out=set()
    def visit(e):
        if e is None: return
        if isinstance(e, Name):
            if e.name in {'row','item','value'}: out.add(f'{source}[*]')
            return
        if isinstance(e, (Field, Property)):
            field_name = getattr(e, 'name', None)
            if isinstance(e.base, Name) and e.base.name in {'row','item','value'} and field_name:
                out.add(f'{source}[*].{field_name}')
            else:
                visit(e.base)
            return
        if isinstance(e,(Binary,Compare,Logical)):
            visit(e.left); visit(getattr(e,'right',None)); return
        if isinstance(e,Call):
            for a in e.args: visit(a)
    visit(expr)
    return out or {f'{source}[*]'}

def _static_expr(expr, row):
    """Small pure evaluator for compile-time literal-data predicates."""
    if isinstance(expr, Name):
        if expr.name in row: return row[expr.name]
        return None
    if isinstance(expr, Field):
        if isinstance(expr.base, Name) and expr.base.name in {"row", "item"}: return row.get(expr.name)
        base = _static_expr(expr.base, row)
        if isinstance(base, dict): return base.get(expr.name)
        return None
    if isinstance(expr, Literal): return expr.value
    if isinstance(expr, Binary):
        a,b=_static_expr(expr.left,row),_static_expr(expr.right,row)
        if a is None or b is None: return None
        return {"+":lambda:a+b,"-":lambda:a-b,"*":lambda:a*b,"/":lambda:a/b,"^":lambda:a**b}.get(expr.op,lambda:None)()
    if isinstance(expr, Compare):
        a,b=_static_expr(expr.left,row),_static_expr(expr.right,row)
        if a is None or b is None: return None
        return {">":a>b,"<":a<b,">=":a>=b,"<=":a<=b,"==":a==b,"!=":a!=b}.get(expr.op)
    if isinstance(expr, Logical):
        a=_static_expr(expr.left,row)
        if expr.op == 'not': return None if a is None else not a
        b=_static_expr(expr.right,row)
        if a is None or b is None: return None
        return (bool(a) and bool(b)) if expr.op == 'and' else (bool(a) or bool(b))
    return None


def _shape_from_rows(rows, reason):
    ranges=[]
    if rows:
        keys=sorted(set().union(*(r.keys() for r in rows)))
        for key in keys:
            vals=[r.get(key) for r in rows]
            if vals and all(isinstance(v,(int,float)) and not isinstance(v,bool) for v in vals):
                ranges.append((key,float(min(vals)),float(max(vals))))
    n=len(rows)
    return DataShape(n,n,True,tuple(ranges),"linear",reason)


def _static_shapes(module):
    out={}
    for ds in getattr(module,"datasets",[]): out[ds.name]=_shape_from_rows(ds.rows,"literal data declaration")
    rows=getattr(module,"people",None)
    if rows and "people" not in out:
        out["people"]=_shape_from_rows([{"name":r.name,"age":r.age} for r in rows],"parsed built-in people dataset")
    for op in getattr(module,"sequences",[]):
        if op.target is not None:
            out[op.result]=DataShape(1,op.steps,False,(),"goal-search","goal-directed transition sequence")
            continue
        if op.until is None:
            out[op.result]=DataShape(op.steps,op.steps,True,(),"linear","sequence has a fixed step count")
        else:
            out[op.result]=DataShape(1,op.steps,False,(),"linear","bounded sequence with semantic termination condition")
    for op in getattr(module,"satisfy_goals",[]):
        size=1
        for _,lo,hi in op.variables: size*=hi-lo+1
        ranges=tuple((name,float(lo),float(hi)) for name,lo,hi in op.variables)
        out[op.result]=DataShape(size,size,True,ranges,"constraint-search","finite Cartesian constraint domain")
    for op in getattr(module,"aggregates",[]): out[op.result]=DataShape(1,1,True,(),"constant","aggregate produces one scalar result")
    for op in getattr(module,"reduces",[]): out[op.result]=DataShape(1,1,True,(),"constant","reduce produces one scalar result")
    for op in getattr(module,"path_goals",[]): out[op.result]=DataShape(1,1,True,(),"graph-search","path goal produces one path result")
    if getattr(module,"bodies",None): out["bodies"]=DataShape(len(module.bodies),len(module.bodies),True,(),"linear","body declarations")
    if getattr(module,"circles",None): out["circles"]=DataShape(len(module.circles),len(module.circles),True,(),"linear","circle declarations")
    if getattr(module,"graphs",None):
        for graph in module.graphs: out[graph.name]=DataShape(len(graph.edges),len(graph.edges),True,(),"graph-search","literal graph edge declaration")
    changed=True
    while changed:
        changed=False
        for op in getattr(module,"filters",[]):
            if op.source in out and op.result not in out:
                src=out[op.source]
                exact_count=None
                source_rows=next((d.rows for d in module.datasets if d.name==op.source),None)
                if source_rows is not None:
                    vals=[_static_expr(op.predicate.expr,r) for r in source_rows]
                    if all(v is not None for v in vals): exact_count=sum(bool(v) for v in vals)
                if exact_count is not None:
                    out[op.result]=DataShape(exact_count,exact_count,True,src.numeric_ranges,"linear","predicate evaluated over literal source data")
                else:
                    out[op.result]=DataShape(0,src.upper,False,src.numeric_ranges,"linear",f"filter result bounded by source '{op.source}'")
                changed=True
        for ops in (getattr(module,"sorts",[]),getattr(module,"maps",[])):
            for op in ops:
                if op.source in out and op.result not in out:
                    src=out[op.source]; out[op.result]=DataShape(src.lower,src.upper,src.exact,src.numeric_ranges,"nlogn" if op.__class__.__name__=='SortOp' else "linear",f"{op.__class__.__name__.lower()} preserves source cardinality"); changed=True
    return out


def _static_cardinalities(module):
    return {k:(v.cardinality,v.exact and "exact" or "bounded",v.reason) for k,v in _static_shapes(module).items()}


def _node_shape(kind,result,source,module,shapes):
    if result in shapes: return shapes[result]
    if kind in {"filter","sort","map","goal:select","conditional-pipeline"} and source in shapes: return shapes[source]
    if kind in {"aggregate","reduce","goal:path"}: return DataShape(1,1,True,(),"constant","single semantic result")
    return None

def _node_cardinality(kind, result, source, module, known):
    if kind in {"aggregate", "reduce", "goal:path", "state:init", "state:set", "state:read", "effect:show"}:
        key = result
        if key in known:
            return known[key]
        if kind in {"aggregate", "reduce", "goal:path"}:
            return (1, "exact", "single semantic result")
        return (None, "unknown", "not a collection result")
    if kind in {"filter", "sort", "map", "goal:select"} and source in known:
        return known[source]
    if kind == "sequence" and result in known:
        return known[result]
    if kind == "goal:satisfy" and result in known:
        return known[result]
    if result in known:
        return known[result]
    return (None, "unknown", "input size is not statically known")


def _expr_has_io(expr):
    if isinstance(expr, Call):
        if expr.name in {"read", "write", "read_lines", "write_lines", "exists", "file_size", "is_file", "is_directory", "list_directory", "list_files", "list_directories", "make_directory", "make_directories", "remove_directory", "remove_directory_tree", "remove_file", "copy_file", "move_file", "arguments", "environment", "run_process", "run_program", "run_program_with_environment", "current_directory", "platform_name", "process_id", "sleep_seconds", "home_directory", "temp_directory", "executable_path", "command_exists"}:
            return True
        return any(_expr_has_io(a) for a in expr.args)
    if isinstance(expr, (Binary, Compare, Logical)):
        return _expr_has_io(expr.left) or (getattr(expr, "right", None) is not None and _expr_has_io(expr.right))
    if isinstance(expr, (Field, Property)):
        return _expr_has_io(expr.base)
    return False

def _numeric_predicate_selectivity(expr, ranges):
    """Infer selectivity for simple numeric predicates from known value ranges.

    The result is a planning estimate, not a runtime statistic. For a single
    monotone comparison over a known interval we can compute the fraction of
    that interval satisfying the predicate. Logical AND/OR combine independent
    interval estimates conservatively. Unsupported expressions return None.
    """
    if expr is None:
        return None
    if isinstance(ranges, dict):
        ranges = dict(ranges)
    else:
        ranges = {name: (lo, hi) for name, lo, hi in (ranges or ())}

    def operand(e):
        if isinstance(e, Name) and e.name in ranges:
            return (e.name, ranges[e.name][0], ranges[e.name][1])
        if isinstance(e, Field) and isinstance(e.base, Name) and e.base.name in {"row", "item", "value"} and e.name in ranges:
            return (e.name, ranges[e.name][0], ranges[e.name][1])
        if isinstance(e, Literal) and isinstance(e.value, (int, float)) and not isinstance(e.value, bool):
            return (None, float(e.value), float(e.value))
        return None

    def compare(e):
        if not isinstance(e, Compare):
            return None
        left, right = operand(e.left), operand(e.right)
        if left is None or right is None:
            return None
        if left[0] is not None and right[0] is None:
            lo, hi, op, threshold = left[1], left[2], e.op, right[1]
        elif right[0] is not None and left[0] is None:
            lo, hi, op, threshold = right[1], right[2], e.op, left[1]
            op = {">":"<", "<":">", ">=":"<=", "<=":">=", "==":"==", "!=":"!="}.get(op, op)
        else:
            return None
        width = hi - lo
        if width <= 0:
            return 1.0 if ((op == "==" and lo == threshold) or (op == "!=" and lo != threshold) or
                            (op == ">" and lo > threshold) or (op == ">=" and lo >= threshold) or
                            (op == "<" and lo < threshold) or (op == "<=" and lo <= threshold)) else 0.0
        if op == ">":
            return max(0.0, min(1.0, (hi - max(lo, threshold)) / width))
        if op == ">=":
            return max(0.0, min(1.0, (hi - max(lo, threshold)) / width))
        if op == "<":
            return max(0.0, min(1.0, (min(hi, threshold) - lo) / width))
        if op == "<=":
            return max(0.0, min(1.0, (min(hi, threshold) - lo) / width))
        if op == "==":
            return 0.0 if threshold < lo or threshold > hi else min(1.0, 1.0 / max(1.0, width))
        if op == "!=":
            return 1.0 if threshold < lo or threshold > hi else max(0.0, 1.0 - 1.0 / max(1.0, width))
        return None

    if isinstance(expr, Compare):
        return compare(expr)
    if isinstance(expr, Logical):
        a = _numeric_predicate_selectivity(expr.left, ranges)
        b = _numeric_predicate_selectivity(expr.right, ranges)
        if a is None or b is None:
            return None
        if expr.op == "and":
            return max(0.0, min(a, b))
        if expr.op == "or":
            return min(1.0, max(a, b))
        return None
    return None

def _node_expr(module, kind, result):
    for attr in ("bindings", "filters", "sorts", "maps", "aggregates", "reduces", "sequences", "conditional_pipelines"):
        for op in getattr(module, attr, []):
            if getattr(op, "result", None) == result:
                if attr == "conditional_pipelines":
                    return getattr(op, "condition", None)
                for field in ("expr", "predicate"):
                    value = getattr(op, field, None)
                    if value is not None:
                        return getattr(value, "expr", value)
    return None

def _function_capture_names_for_module(module):
    """Return lexical captures for user functions, including nested closures."""
    from .function_effects import analyze_function_effects
    return {summary.function: set(summary.captures) for summary in analyze_function_effects(module)}


def _function_state_reads_for_module(module):
    """Return concrete state names observed by each function/closure.

    Global states are not lexical captures in the narrow closure sense, but
    they are still captured runtime dependencies.  Keep that distinction
    explicit so scheduler conflict analysis can see them.
    """
    state_names = {getattr(st, 'name', st) for st in getattr(module, 'states', ())}
    result = {}
    from .ast import Name
    from dataclasses import fields, is_dataclass

    def walk(obj):
        if obj is None or isinstance(obj, (str, bytes, int, float, bool)):
            return
        if isinstance(obj, (tuple, list, set, frozenset)):
            for item in obj:
                yield from walk(item)
            return
        if isinstance(obj, dict):
            for item in obj.values():
                yield from walk(item)
            return
        if is_dataclass(obj):
            yield obj
            for field in fields(obj):
                yield from walk(getattr(obj, field.name))

    def visit(fn, qualified):
        reads = {obj.name for obj in walk(fn.body) if isinstance(obj, Name) and obj.name in state_names}
        result[qualified] = reads
        scope = set(name for name, _ in getattr(fn, 'parameters', ()))
        for stmt in getattr(fn, 'body', ()):
            if stmt.__class__.__name__ == 'FunctionDecl':
                visit(stmt, qualified + '.' + stmt.name)

    for fn in getattr(module, 'functions', ()):
        visit(fn, fn.name)
    return result


def _expr_function_captures(expr, function_captures, aliases=None):
    """Collect lexical captures that a function-valued expression can observe."""
    if expr is None:
        return set()
    aliases = aliases or {}

    def resolve(name):
        seen = set()
        while name in aliases and name not in seen:
            seen.add(name)
            name = aliases[name]
        return name

    if isinstance(expr, Name):
        return set(function_captures.get(resolve(expr.name), ()))
    if isinstance(expr, Call):
        out = set(function_captures.get(resolve(expr.name), ()))
        for arg in expr.args:
            out.update(_expr_function_captures(arg, function_captures, aliases))
        return out
    if isinstance(expr, (Binary, Compare, Logical)):
        return _expr_function_captures(expr.left, function_captures, aliases) | _expr_function_captures(getattr(expr, 'right', None), function_captures, aliases)
    if isinstance(expr, (Field, Property)):
        return _expr_function_captures(expr.base, function_captures, aliases)
    return set()


def _function_effects_for_module(module):
    """Return inferred effects for user-defined functions without making the IR depend on a backend."""
    from .function_effects import analyze_function_effects
    result = {summary.function: set(summary.effects) for summary in analyze_function_effects(module)}
    # Preserve inferred contracts through simple first-class aliases such as
    # `let transform = double`; the alias is then treated like the original
    # function when a collection operation is analyzed.
    aliases = {}
    binding_exprs = {}
    for binding in getattr(module, 'bindings', []):
        expr = getattr(binding, 'expr', None)
        binding_exprs[binding.name] = expr
        if isinstance(expr, Name):
            aliases[binding.name] = expr.name
    # Instantiate contracts returned by generic higher-order factories, e.g.
    # `let lifted = lift(load)` where lift returns Function<..., E>.
    # The function-level analyzer records E on `lift.__return__`; bind it to
    # the concrete effect of the corresponding function-valued argument.
    summaries = analyze_function_effects(module)
    returned = {s.function + '.__return__': set(s.returned_function_effects)
                for s in summaries if s.returned_function_effects}
    effect_specs = _function_effect_specs(module)
    for binding in getattr(module, 'bindings', []):
        expr = getattr(binding, 'expr', None)
        if not isinstance(expr, Call):
            continue
        raw = returned.get(expr.name + '.__return__', set())
        if not raw:
            continue
        instantiated = set()
        for effect in raw:
            if isinstance(effect, str) and effect.startswith('$'):
                for marker, index in effect_specs.get(expr.name, ()):
                    if marker == effect and index < len(expr.args):
                        instantiated.update(_effect_contract_for_argument(expr.args[index], result))
            else:
                instantiated.add(effect)
        if instantiated:
            result[binding.name] = instantiated

    # Fixed point makes multi-level aliases observable to higher-order ops.
    changed = True
    while changed:
        changed = False
        for alias, target in list(aliases.items()):
            resolved = aliases.get(target, target)
            if resolved != target:
                aliases[alias] = resolved
                changed = True
        for name, expr in binding_exprs.items():
            if isinstance(expr, Call) and expr.name == 'compose':
                inferred = set()
                for arg in expr.args:
                    if isinstance(arg, Name):
                        target = aliases.get(arg.name, arg.name)
                        inferred.update(result.get(target, ()))
                if inferred and result.get(name, set()) != inferred:
                    result[name] = inferred
                    changed = True
    for alias, target in aliases.items():
        if target in result:
            result[alias] = set(result[target])
    return result


def _function_effect_specs(module):
    """Map function names to effect-polymorphic parameter positions.

    A signature such as ``Function<Number, Number, E>`` makes ``E`` depend on
    the corresponding function argument. The representation is deliberately
    small: ``name -> (effect variable, argument index)``.
    """
    specs = {}
    aliases = {}
    functions = {fn.name: fn for fn in getattr(module, 'functions', [])}
    for fn in functions.values():
        for index, (param_name, ref) in enumerate(getattr(fn, 'parameters', [])):
            if getattr(ref, 'name', None) != 'Function':
                continue
            args = list(getattr(ref, 'args', ()))
            if not args:
                continue
            markers = []
            while args and not getattr(args[-1], 'args', ()) and len(args[-1].name) == 1 and args[-1].name.isupper():
                markers.append('$' + args.pop().name)
            for marker in reversed(markers):
                specs.setdefault(fn.name, []).append((marker, index))
    for binding in getattr(module, 'bindings', []):
        expr = getattr(binding, 'expr', None)
        if isinstance(expr, Name):
            aliases[binding.name] = expr.name
    changed = True
    while changed:
        changed = False
        for alias, target in list(aliases.items()):
            resolved = aliases.get(target, target)
            if resolved != target:
                aliases[alias] = resolved
                changed = True
    for alias, target in aliases.items():
        if target in specs:
            specs[alias] = list(specs[target])
    return {name: tuple(value) for name, value in specs.items()}


def _effect_contract_for_argument(arg, function_effects):
    if isinstance(arg, Name):
        return set(function_effects.get(arg.name, ()))
    if isinstance(arg, Call):
        return _expr_function_effects(arg, function_effects)
    return set()

def _expr_function_effects(expr, function_effects, effect_specs=None):
    """Collect effects of user-defined calls, instantiating effect variables."""
    if expr is None:
        return set()
    if isinstance(expr, Name):
        return {e for e in function_effects.get(expr.name, ()) if not str(e).startswith('$')}
    if isinstance(expr, Call):
        effect_specs = effect_specs or {}
        raw = set(function_effects.get(expr.name, ()))
        variables = {e for e in raw if str(e).startswith('$')}
        effects = raw - variables
        for variable, index in effect_specs.get(expr.name, ()):
            if variable in variables and index < len(expr.args):
                effects.update(_effect_contract_for_argument(expr.args[index], function_effects))
        # Higher-order calls inherit contracts of function-valued arguments.
        for arg in expr.args:
            effects.update(_expr_function_effects(arg, function_effects, effect_specs))
        return effects
    if isinstance(expr, (Binary, Compare, Logical)):
        effects = _expr_function_effects(expr.left, function_effects)
        right = getattr(expr, 'right', None)
        if right is not None:
            effects.update(_expr_function_effects(right, function_effects))
        return effects
    if isinstance(expr, (Field, Property)):
        return _expr_function_effects(expr.base, function_effects)
    return set()


def _collection_schema(module, value_type):
    if value_type is None:
        return None
    try:
        from .types import is_list, list_element, RecordSchema, record_schema
    except Exception:
        return None
    item = list_element(value_type) if is_list(value_type) else value_type
    if getattr(item, "name", None) != "Record":
        return None
    args = getattr(item, "args", ())
    record_name = getattr(args[0], "name", None) if args else None
    if not record_name:
        return None
    registry = getattr(module, "_record_schemas", {}) or {}
    schema = registry.get(record_name)
    return schema


def _record_field_provenance(module, kind, result, source, expr_node, output_schema):
    """Infer conservative provenance for fields produced by a Record map.

    A field is marked direct when its constructor argument is exactly
    ``row.field``; derived when the expression contains one or more row-field
    references; unknown when the mapping is delegated to an opaque function.
    This is deliberately conservative: provenance may enable a recompute
    candidate, but never proves semantic equivalence by itself.
    """
    if kind != 'map' or output_schema is None:
        return ()
    fields = tuple(getattr(output_schema, 'fields', ()) or ())
    if not fields or expr_node is None:
        return ()
    from .ast import Field, Name, Call, Binary, Compare, Logical, Conditional, Property

    def refs(expr):
        if isinstance(expr, Field):
            if isinstance(expr.base, Name) and expr.base.name in {'row','item','value'}:
                return (expr.name,)
            return refs(expr.base)
        if isinstance(expr, (Binary, Compare, Logical)):
            return tuple(dict.fromkeys(refs(expr.left) + refs(getattr(expr, 'right', None))))
        if isinstance(expr, Conditional):
            return tuple(dict.fromkeys(refs(expr.condition) + refs(expr.then_expr) + refs(expr.else_expr)))
        if isinstance(expr, Call):
            out=()
            for arg in expr.args:
                out += refs(arg)
            return tuple(dict.fromkeys(out))
        if isinstance(expr, Property):
            if isinstance(expr.base, Name) and expr.base.name in {'row','item','value'}:
                return (expr.name,)
            return refs(expr.base)
        return ()

    # A constructor call has positional arguments matching the resolved output
    # schema. This covers the normal Record map form: R(row.a, row.b + 1).
    args = getattr(expr_node, 'args', ()) if isinstance(expr_node, Call) else ()
    if not args:
        return tuple((f.name, (), 'unknown') for f in fields)
    out=[]
    for i, field in enumerate(fields):
        arg = args[i] if i < len(args) else None
        source_fields = tuple(dict.fromkeys(refs(arg)))
        if isinstance(arg, (Field, Property)) and isinstance(arg.base, Name) and arg.base.name in {'row','item','value'}:
            certainty='direct'
        elif source_fields:
            certainty='derived'
        else:
            certainty='constant'
        out.append((str(field.name), source_fields, certainty))
    return tuple(out)


def build_execution_ir(module):
    raw=[]
    function_effects = _function_effects_for_module(module)
    function_captures = _function_capture_names_for_module(module)
    function_state_reads = _function_state_reads_for_module(module)
    effect_specs = _function_effect_specs(module)
    function_bindings = {fn.name: f"@fn:{fn.name}" for fn in module.functions}
    property_bindings = {prop.name: f"@prop:{prop.entity_type}.{prop.name}" for prop in module.properties}
    for fn in module.functions:
        refs=_body_names(fn.body)-{name for name,_ in fn.parameters}
        raw.append(('function','@fn:'+fn.name,None,refs,True,True))
    for prop in module.properties: raw.append(('property','@prop:'+prop.entity_type+'.'+prop.name,None,_body_names(prop.body),True,True))
    state_set_counts={}
    for obj in getattr(module, 'ordered_effects', []):
        if obj.__class__.__name__ == 'StateDecl':
            raw.append(('state:init',f'@state:{obj.name}:init',obj.name,_names(obj.expr),False,False))
        elif obj.__class__.__name__ == 'BindingDecl':
            binding_kind = 'group' if isinstance(obj.expr, Call) and obj.expr.name in {'group_by', 'group_count', 'group_sum', 'group_average', 'group_min', 'group_max'} else 'binding'
            raw.append((binding_kind,obj.name,None,_names(obj.expr),True,False))
        elif obj.__class__.__name__ == 'SetStateOp':
            state_set_counts[obj.name]=state_set_counts.get(obj.name,0)+1
            raw.append(('state:set',f'@state:{obj.name}:set:{state_set_counts[obj.name]}',obj.name,_names(obj.expr),False,False))
        elif obj.__class__.__name__ == 'ShowOp':
            pass
    if not getattr(module, 'ordered_effects', []):
        for st in module.states: raw.append(('state:init',f'@state:{st.name}:init',st.name,_names(st.expr),False,False))
        for b in module.bindings:
            binding_kind = 'binding'
            expr = getattr(b, 'expr', None)
            if isinstance(expr, Call) and expr.name in {'group_by', 'group_count', 'group_sum', 'group_average', 'group_min', 'group_max'}:
                binding_kind = 'group'
            raw.append((binding_kind,b.name,None,_names(b.expr),True,False))
        for index, st in enumerate(module.state_sets): raw.append(('state:set',f'@state:{st.name}:set:{index+1}',st.name,_names(st.expr),False,False))
    for op in module.sequences:
        if op.target is not None:
            continue  # represented as goal:transition below
        refs = _names(op.initial) | _names(op.expr)
        if op.target is not None:
            refs |= _names(op.target)
            for candidate in op.candidates:
                refs |= _names(candidate)
        raw.append(('sequence', op.result, None, refs, True, False))
    collection_raw = []
    for op in module.filters: collection_raw.append(('filter',op.result,op.source,_names(op.predicate.expr),True,False,op))
    for op in module.sorts: collection_raw.append(('sort',op.result,op.source,_names(op.spec.expr),True,False,op))
    for op in module.maps: collection_raw.append(('map',op.result,op.source,_names(op.expr),True,False,op))
    for op in module.aggregates: collection_raw.append(('aggregate',op.result,op.source,_names(op.expr),True,False,op))
    for op in module.reduces: collection_raw.append(('reduce',op.result,op.source,_names(op.initial)|_names(op.expr),True,False,op))
    for op in getattr(module, 'conditional_pipelines', []):
        refs = _names(op.condition)
        for stage_kind, stage_expr in tuple(op.then_stages) + tuple(op.else_stages):
            if stage_kind == 'sort':
                refs |= _names(stage_expr.expr)
            elif stage_kind == 'aggregate':
                refs |= _names(stage_expr[1])
            elif stage_kind == 'reduce':
                refs |= _names(stage_expr[0]) | _names(stage_expr[1])
            else:
                refs |= _names(stage_expr.expr if hasattr(stage_expr, 'expr') else stage_expr)
        collection_raw.append(('conditional-pipeline', op.result, op.source, refs, True, False, op))
    from .ast import source_span_of
    collection_raw.sort(key=lambda item: (
        source_span_of(item[6]).start.line if source_span_of(item[6]) else 10**9,
        source_span_of(item[6]).start.column if source_span_of(item[6]) else 10**9,
    ))
    raw.extend(item[:6] for item in collection_raw)
    if getattr(module, 'bodies', None) or getattr(module, 'simulation', None) or getattr(module, 'gravity', False):
        body_refs = {b.name for b in getattr(module, 'bodies', [])}
        raw.append(('physics.gravity', '@physics:gravity', None, body_refs, False, True))
    from .semantic_graph import build_semantic_graph
    for n in build_semantic_graph(module).nodes:
        if n.kind in {'select','path','satisfy'}: raw.append(('goal:'+n.kind,n.result,n.source,set(n.dependencies)|set(n.external_sources),True,False))
        elif n.kind == 'goal:transition': raw.append(('goal:transition',n.result,n.source,set(n.dependencies)|set(n.external_sources),True,False))
    for index, show in enumerate(module.shows):
        raw.append(('effect:show',f'@show:{index+1}',None,_names(show.target),False,False))

    semantic_collection_types = getattr(module, "_collection_types", {}) or {}
    static_shapes = _static_shapes(module)
    known_cardinalities = {k:(v.cardinality,v.exact and "exact" or "bounded",v.reason) for k,v in static_shapes.items()}
    state_names={st.name for st in module.states}
    produced={}; nodes=[]; previous_effect=None
    last_state_write={}; outstanding_state_reads={name:set() for name in state_names}; outstanding_state_read_consumers={name:set() for name in state_names}; read_counter=0

    def add_state_reads(refs):
        nonlocal read_counter
        read_bindings={}
        for state_name in sorted(set(refs) & state_names):
            read_counter += 1
            binding=f'@state:{state_name}:read:{read_counter}'
            deps=set()
            if state_name in last_state_write: deps.add(last_state_write[state_name])
            nodes.append(ExecutionNode(binding,'state:read',state_name,tuple(sorted(deps)),(),False,False,True,'read-only',False,('state-read',),(state_name,),(),( ),parse_regions((state_name,))))
            outstanding_state_reads[state_name].add(binding)
            read_bindings[state_name]=binding
        return read_bindings

    for kind,result,source,refs,pure,definition in raw:
        state_reads=add_state_reads(refs)
        resolved=set()
        for ref in refs:
            if ref in state_reads: resolved.add(state_reads[ref])
            elif ref in function_bindings: resolved.add(function_bindings[ref])
            elif ref in property_bindings: resolved.add(property_bindings[ref])
            elif ref.startswith('@fn:') and ref[4:] in function_bindings: resolved.add(ref)
            elif ref.startswith('@prop:') and ref[6:] in {prop.name for prop in module.properties}: resolved.add(ref)
            elif ref.startswith('@fn:') and ref[4:] in produced: resolved.add(produced[ref[4:]])
            elif ref.startswith('@prop:') and ref[6:] in produced: resolved.add(produced[ref[6:]])
            elif ref in produced: resolved.add(produced[ref])
            elif ref not in {'row','item','acc','value','self'} and ref not in state_names: resolved.add(ref)
        if source and source in produced: resolved.add(produced[source])
        if kind == 'effect:show' and any(n.kind == 'physics.gravity' for n in nodes):
            resolved.add(next(n.binding for n in nodes if n.kind == 'physics.gravity'))
        existing={n.binding for n in nodes}
        deps=set(r for r in resolved if r in existing or r.startswith('@fn:') or r.startswith('@prop:'))
        binding=result if definition else f'{result}#{sum(1 for n in nodes if n.result==result and not n.definition)+1}'
        shape = _node_shape(kind, result, source, module, static_shapes)
        cardinality, cardinality_confidence, cardinality_reason = _node_cardinality(kind, result, source, module, known_cardinalities)
        if shape is not None and shape.cardinality is not None:
            cardinality, cardinality_confidence, cardinality_reason = shape.cardinality, ("exact" if shape.exact else "bounded"), shape.reason
        memory_reads=tuple(sorted(state_reads))
        memory_writes=()
        memory_regions=set()
        if kind in {'filter','sort','map','aggregate','reduce','conditional-pipeline','sequence'} and source:
            expr_for_region = None
            if kind == 'filter': expr_for_region = next((x.predicate.expr for x in module.filters if x.result == result), None)
            elif kind == 'sort': expr_for_region = next((x.spec.expr for x in module.sorts if x.result == result), None)
            elif kind == 'map': expr_for_region = next((x.expr for x in module.maps if x.result == result), None)
            elif kind == 'aggregate': expr_for_region = next((x.expr for x in module.aggregates if x.result == result), None)
            elif kind == 'reduce':
                op_for_region = next((x for x in module.reduces if x.result == result), None)
                expr_for_region = op_for_region.expr if op_for_region is not None else None
            elif kind == 'conditional-pipeline':
                op_for_region = next((x for x in getattr(module, 'conditional_pipelines', []) if x.result == result), None)
                expr_for_region = op_for_region.condition if op_for_region is not None else None
            memory_regions = _collection_regions(expr_for_region, source)
        expr_node = _node_expr(module, kind, result)
        function_aliases = {
            b.name: b.expr.name for b in getattr(module, 'bindings', [])
            if isinstance(getattr(b, 'expr', None), Name)
        }
        capture_names = _expr_function_captures(expr_node, function_captures, function_aliases)
        captured_states = capture_names & state_names
        if isinstance(expr_node, Name):
            target = function_aliases.get(expr_node.name, expr_node.name)
            captured_states.update(function_state_reads.get(target, ()))
        elif isinstance(expr_node, Call):
            target = function_aliases.get(expr_node.name, expr_node.name)
            captured_states.update(function_state_reads.get(target, ()))
            for arg in expr_node.args:
                if isinstance(arg, Name):
                    captured_states.update(function_state_reads.get(function_aliases.get(arg.name, arg.name), ()))
        captured_states.update(set(state_reads) & state_names)
        for captured_state in sorted(captured_states):
            if captured_state in last_state_write:
                deps.add(last_state_write[captured_state])
        memory_reads=tuple(sorted(set(state_reads) | captured_states))
        if kind == 'effect:show': effects=('IO',); pure=False; deterministic=True; access='read-only'; order_sensitive=True
        elif kind == 'state:init': effects=('state',); pure=False; deterministic=True; access='write'; order_sensitive=True; memory_writes=(result.split(':')[1],); memory_reads=()
        elif kind == 'state:set': effects=('state',); pure=False; deterministic=True; access='write'; order_sensitive=True; memory_writes=(result.split(':')[1],)
        elif _expr_has_io(expr_node): effects=('IO',); pure=False; deterministic=True; access='read-write'; order_sensitive=True
        else:
            inferred = _expr_function_effects(expr_node, function_effects, effect_specs)
            effects = tuple(sorted(inferred))
            unsafe = {'state-write', 'io', 'external'} & set(effects)
            pure = not effects
            deterministic = True
            access = 'read-write' if unsafe else 'read-only'
            order_sensitive = bool(unsafe)
        if kind in {'state:init','state:set'}:
            target_state=result.split(':')[1]
            if kind == 'state:set' and target_state in last_state_write:
                deps.add(last_state_write[target_state])
            # A write must wait for the computations that consumed the
            # previous read. Depending only on the read node itself would
            # allow the write and its reader to enter the same scheduler
            # batch, changing the source-visible state boundary.
            deps.update(outstanding_state_read_consumers.get(target_state,set()))
            outstanding_state_reads[target_state].clear()
            outstanding_state_read_consumers[target_state].clear()
        if kind == 'effect:show' and previous_effect and previous_effect not in deps: deps.add(previous_effect)
        # A function/closure may read state without a syntactic state name in
        # the calling expression. Register that consumer so a later state write
        # cannot cross the call.
        for captured_state in captured_states:
            outstanding_state_read_consumers.setdefault(captured_state, set()).add(binding)
        deps=tuple(sorted(deps)); ext=tuple(sorted(r for r in resolved if r not in deps and not r.startswith('@')))
        hints=[]
        if kind == "filter" and source and shape is not None:
            inferred = _numeric_predicate_selectivity(expr_node, shape.numeric_ranges)
            if inferred is not None:
                hints.append(f"filter-selectivity={max(0.0, min(1.0, inferred)):.6f}")
        elif kind == "goal:select" and shape is not None:
            goal = next((x for x in getattr(module, "goals", []) if x.result == result), None)
            predicate = getattr(getattr(goal, "predicate", None), "expr", None) if goal is not None else None
            inferred = _numeric_predicate_selectivity(predicate, shape.numeric_ranges)
            if inferred is not None:
                hints.append(f"goal-selectivity={max(0.0, min(1.0, inferred)):.6f}")
        elif kind == "goal:path":
            goal = next((x for x in getattr(module, "path_goals", []) if x.result == result), None)
            if goal is not None:
                graph = next((g for g in getattr(module, "graphs", []) if g.name == goal.source), None)
                if graph is not None:
                    edges = list(graph.edges)
                    vertices = {v for edge in edges for v in edge[:2]}
                    positive = [float(edge[2]) for edge in edges if len(edge) > 2 and float(edge[2]) >= 0]
                    hints.append(f"path-graph-nodes={len(vertices)}")
                    hints.append(f"path-graph-edges={len(edges)}")
                    if vertices:
                        density = len(edges) / max(1, len(vertices) * max(1, len(vertices) - 1))
                        hints.append(f"path-graph-density={density:.6f}")
                    if positive:
                        hints.append(f"path-min-edge-cost={min(positive):.6f}")
                    all_bidir = bool(edges) and all(bool(edge[3]) for edge in edges)
                    if all_bidir:
                        hints.append("path-all-bidirectional=true")
                    if positive and all_bidir:
                        hints.append("path-nonnegative-costs=true")
                    # The reference path operation returns one path, but its
                    # search space is governed by the graph. Keep this as a
                    # planning hint rather than changing result cardinality.
                    search_factor = min(1.0, len(edges) / max(1, len(vertices) * len(vertices)))
                    hints.append(f"path-search-selectivity={search_factor:.6f}")
        elif kind == "goal:satisfy":
            goal = next((x for x in getattr(module, "satisfy_goals", []) if x.result == result), None)
            if goal is not None:
                try:
                    from .goal_plan import propagate_integer_bounds
                    narrowed = propagate_integer_bounds(goal.variables, goal.constraints)
                    original = 1
                    remaining = 1
                    for name, lo, hi in goal.variables:
                        original *= max(0, int(hi) - int(lo) + 1)
                        nlo, nhi = narrowed.get(name, (lo, hi))
                        remaining *= max(0, int(nhi) - int(nlo) + 1)
                    if original > 0:
                        reduction = max(0.0, min(1.0, remaining / original))
                        hints.append(f"satisfy-search-selectivity={reduction:.6f}")
                        if remaining == 0:
                            hints.append("satisfy-search-space-empty")
                except Exception:
                    # Planning hints must never make IR construction fail.
                    pass
        if kind == "reduce" and source:
            upstream_ops = {op.result for op in getattr(module, "filters", [])} | {op.result for op in getattr(module, "maps", [])}
            if source in upstream_ops:
                hints.append("fusable-filter-map-reduce")
        input_type = _type_text(semantic_collection_types.get(source)) if source in semantic_collection_types else None
        output_type = _type_text(semantic_collection_types.get(result)) if result in semantic_collection_types else None
        input_schema_obj = _collection_schema(module, semantic_collection_types.get(source) if source in semantic_collection_types else None)
        output_schema_obj = _collection_schema(module, semantic_collection_types.get(result) if result in semantic_collection_types else None)
        provenance = _record_field_provenance(module, kind, result, source, expr_node, output_schema_obj)
        nodes.append(ExecutionNode(binding,kind,None if definition else result,deps,ext,pure,definition,deterministic,access,order_sensitive,effects,memory_reads,memory_writes,tuple(sorted(memory_regions)),parse_regions(tuple(sorted(memory_regions))),cardinality,cardinality_confidence,cardinality_reason,shape,tuple(hints),input_type,output_type,input_schema_obj,output_schema_obj,provenance))
        if state_reads and kind not in {'state:init','state:set'}:
            for state_name in state_reads:
                outstanding_state_read_consumers[state_name].add(binding)
        if kind in {'state:init','state:set'}:
            target_state=result.split(':')[1]
            last_state_write[target_state]=binding
        if kind == 'effect:show': previous_effect=binding
        elif not definition: produced[result]=binding
    # Collection operations are stored in AST buckets by operation kind, while
    # source syntax may reference a producer that appears in a different bucket
    # (for example `adults = people where ...` followed by `older = adults map ...`).
    # The first dependency pass is intentionally single-pass, so repair these
    # source edges after every producer node is known.  This keeps the execution
    # plan topological even when producer/consumer operation kinds are interleaved
    # in source order.
    node_positions = {n.binding: i for i, n in enumerate(nodes)}
    producers = {}
    for i, n in enumerate(nodes):
        if n.result is not None:
            producers.setdefault(n.result, []).append((i, n.binding))
    collection_kinds = {'filter', 'sort', 'map', 'group', 'aggregate', 'reduce', 'conditional-pipeline'}
    repaired = []
    operation_ordinals = {}
    for i, n in enumerate(nodes):
        if n.kind not in collection_kinds or not n.result:
            repaired.append(n)
            continue
        source_ops = {
            'filter': getattr(module, 'filters', []),
            'sort': getattr(module, 'sorts', []),
            'map': getattr(module, 'maps', []),
            'aggregate': getattr(module, 'aggregates', []),
            'reduce': getattr(module, 'reduces', []),
            'conditional-pipeline': getattr(module, 'conditional_pipelines', []),
        }.get(n.kind, ())
        matching_ops = [op for op in source_ops if op.result == n.result]
        from .ast import source_span_of
        matching_ops.sort(key=lambda op: (
            source_span_of(op).start.line if source_span_of(op) else 10**9,
            source_span_of(op).start.column if source_span_of(op) else 10**9,
        ))
        ordinal_key = (n.kind, n.result)
        ordinal = operation_ordinals.get(ordinal_key, 0)
        operation_ordinals[ordinal_key] = ordinal + 1
        source = matching_ops[ordinal].source if ordinal < len(matching_ops) else None
        group_source_reference = None
        group_consumer_span = None
        if n.kind == 'group':
            binding_obj = next((b for b in getattr(module, 'bindings', []) if b.name == n.result), None)
            call = getattr(binding_obj, 'expr', None)
            if isinstance(call, Call) and call.args and isinstance(call.args[0], Name):
                source = call.args[0].name
                group_source_reference = source
                group_consumer_span = source_span_of(binding_obj) if binding_obj is not None else None
        if not source or source in {d.name for d in getattr(module, 'datasets', [])} or source in {b.name for b in getattr(module, 'bindings', [])}:
            repaired.append(n)
            continue
        candidates = [(pos, binding) for pos, binding in producers.get(source, ()) if pos < i]
        if n.kind == 'group' and not candidates and group_source_reference:
            # Group calls are represented as ordinary bindings and are
            # collected before filter/map/sort operations in the AST buckets.
            # Their collection producer can therefore appear later in this
            # initial IR list even though its source expression precedes the
            # group call in the program. Resolve by source location rather
            # than mistaking the producer for an unresolved external input.
            producer_spans = {}
            for collection_ops in (
                getattr(module, 'filters', []), getattr(module, 'sorts', []),
                getattr(module, 'maps', []), getattr(module, 'aggregates', []),
                getattr(module, 'reduces', []),
                getattr(module, 'conditional_pipelines', []),
            ):
                for operation in collection_ops:
                    span = source_span_of(operation)
                    if span is not None:
                        producer_spans.setdefault(operation.result, []).append(span)
            if group_consumer_span is not None:
                collection_producers = []
                for pos, binding in producers.get(source, ()):
                    producer = next((candidate for candidate in nodes if candidate.binding == binding), None)
                    if producer is not None and producer.kind in collection_kinds:
                        collection_producers.append((pos, binding))
                spans = producer_spans.get(source, ())
                for ordinal, candidate in enumerate(collection_producers):
                    if ordinal >= len(spans):
                        continue
                    span = spans[ordinal]
                    if (span.start.line, span.start.column) < (
                        group_consumer_span.start.line, group_consumer_span.start.column
                    ):
                        candidates.append(candidate)
        if candidates:
            # Source-ordered IR uses the latest preceding producer for an
            # in-place rebinding. Group bindings are the exception: their
            # source operation may be stored later in an AST bucket, so the
            # candidate set above is already constrained by source location.
            chosen = max(candidates, key=lambda item: item[0])[1]
            deps = tuple(sorted(set(n.dependencies) | {chosen}))
            ext = tuple(x for x in n.external_sources if x != group_source_reference)
            n = ExecutionNode(n.binding, n.kind, n.result, deps, ext, n.pure, n.definition, n.deterministic, n.access, n.order_sensitive, n.effects, n.memory_reads, n.memory_writes, n.memory_regions, n.memory_region_specs, n.cardinality, n.cardinality_confidence, n.cardinality_reason, n.data_shape, n.optimization_hints, n.input_type, n.output_type, n.input_schema, n.output_schema, n.record_field_provenance)
        repaired.append(n)
    nodes = repaired

    # Resolve Record-field provenance transitively across consecutive maps.
    # A map-local dependency such as ``row.value`` is rewritten to the
    # upstream root fields that actually determine ``value``.  This remains
    # conservative: unknown upstream provenance propagates as unknown, while
    # constants stay independent of the upstream Record.
    by_binding = {n.binding: n for n in nodes}
    by_result = {}
    for n in nodes:
        if n.result is not None:
            by_result.setdefault(n.result, n)

    resolved_cache = {}

    def resolve_node(node, stack=()):
        if node.binding in resolved_cache:
            return resolved_cache[node.binding]
        if node.binding in stack:
            return node.record_field_provenance
        if node.kind != 'map' or not node.record_field_provenance:
            resolved_cache[node.binding] = node.record_field_provenance
            return node.record_field_provenance
        # Find the collection producer that supplies this map's source.
        source = None
        for dep in node.dependencies:
            candidate = by_binding.get(dep)
            if candidate is not None and candidate.result == node.result:
                continue
            if candidate is not None and candidate.output_schema is not None:
                source = candidate
                break
        if source is None:
            resolved_cache[node.binding] = node.record_field_provenance
            return node.record_field_provenance
        upstream = dict((name, (sources, certainty)) for name, sources, certainty
                        in resolve_node(source, stack + (node.binding,)))
        out = []
        for name, sources, certainty in node.record_field_provenance:
            if certainty == 'constant':
                out.append((name, (), 'constant'))
                continue
            root_sources = []
            root_unknown = False
            upstream_derived = False
            for source_name in sources:
                item = upstream.get(source_name)
                if item is None:
                    # The immediate source is the root of the chain (for
                    # example a dataset field with no producer node).
                    root_sources.append(source_name)
                    continue
                parent_sources, parent_certainty = item
                if parent_certainty == 'unknown':
                    root_unknown = True
                if parent_certainty == 'derived':
                    upstream_derived = True
                root_sources.extend(parent_sources)
            root_sources = tuple(dict.fromkeys(root_sources))
            if root_unknown:
                final_certainty = 'unknown'
            elif certainty == 'derived' or upstream_derived or len(root_sources) > 1:
                final_certainty = 'derived'
            else:
                final_certainty = 'direct'
            out.append((name, root_sources, final_certainty))
        result = tuple(out)
        resolved_cache[node.binding] = result
        return result

    propagated = []
    for n in nodes:
        provenance = resolve_node(n)
        if provenance != n.record_field_provenance:
            n = ExecutionNode(n.binding, n.kind, n.result, n.dependencies, n.external_sources,
                              n.pure, n.definition, n.deterministic, n.access, n.order_sensitive,
                              n.effects, n.memory_reads, n.memory_writes, n.memory_regions,
                              n.memory_region_specs, n.cardinality, n.cardinality_confidence,
                              n.cardinality_reason, n.data_shape, n.optimization_hints,
                              n.input_type, n.output_type, n.input_schema, n.output_schema, provenance)
        propagated.append(n)
    nodes = propagated
    return ExecutionIR(tuple(nodes))

def _schema_text(schema):
    if schema is None:
        return None
    fields = getattr(schema, "fields", ())
    return {"name": getattr(schema, "name", None), "fields": tuple((f.name, f.type_name) for f in fields)}


def format_execution_ir(ir):
    lines=['execution.ir {']
    for n in ir.nodes:
        lines += [f'  node "{n.binding}" kind={n.kind}', '    dependencies = '+(', '.join(n.dependencies) if n.dependencies else 'none'), '    external_sources = '+(', '.join(n.external_sources) if n.external_sources else 'none'), '    pure = '+('yes' if n.pure else 'no'), '    deterministic = '+('yes' if n.deterministic else 'no'), '    access = '+n.access, '    order_sensitive = '+('yes' if n.order_sensitive else 'no'), '    reorderable = '+('yes' if n.reorderable else 'no'), '    parallel_safe = '+('yes' if n.parallel_safe else 'no'), '    effects = '+(', '.join(n.effects) if n.effects else 'none')]
        lines.append('    state_reads = '+(', '.join(n.memory_reads) if n.memory_reads else 'none'))
        lines.append('    state_writes = '+(', '.join(n.memory_writes) if n.memory_writes else 'none'))
        lines.append('    state_access = '+n.state_access)
        lines.append('    memory_regions = '+(', '.join(n.memory_regions) if n.memory_regions else 'none'))
        lines.append('    memory_region_model = '+(', '.join(f'{r.scope}:{r.canonical}' for r in n.memory_region_specs) if n.memory_region_specs else 'none'))
        lines.append('    cardinality = '+(str(n.cardinality) if n.cardinality is not None else 'unknown')+' ('+n.cardinality_confidence+'; '+n.cardinality_reason+')')
        if n.data_shape:
            rng=', '.join(f'{k}=[{lo:g},{hi:g}]' for k,lo,hi in n.data_shape.numeric_ranges) or 'none'
            lines.append(f'    data_shape = [{n.data_shape.lower},{n.data_shape.upper}] exact={"yes" if n.data_shape.exact else "no"} complexity={n.data_shape.complexity} ranges={rng}')
        if n.definition:lines.append('    definition = yes')
    lines.append('  execution_order = '+(' -> '.join(ir.topological_order()) if ir.nodes else 'none')); lines.append('}'); return '\n'.join(lines)
