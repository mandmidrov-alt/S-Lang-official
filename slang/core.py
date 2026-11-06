from __future__ import annotations
from dataclasses import dataclass, replace
import math, re, struct
from .ast import (Module, ImportDecl, ModuleDecl, DataDecl, BodyDecl, CircleDecl, Name, Field, Literal, Compare, Logical, Conditional, Binary, Call, Property, Predicate, SortSpec, FilterOp, SortOp, ShowOp, SimulationOp, FunctionDecl, PropertyDecl, EntityDecl, RecordDecl, BindingDecl, TypeRef, ReturnOp, LetOp, IfOp, LocalCollectionOp, MapOp, AggregateOp, ReduceOp, ConditionalPipelineOp, SequenceOp, GoalOp, GraphDecl, PathGoalOp, SatisfyGoalOp, StateDecl, SetStateOp)
from .types import Type, NUMBER, BOOLEAN, TEXT, ANY, RECORD, quantity_type, list_type, list_item_type, is_list, entity_type, record_type, same_or_any, generic_match, substitute_type, type_var, is_type_var, collection_preserve_type, collection_map_type, collection_reduce_type, function_type, is_function, function_result, function_params, function_effects, unify_types
from .domains import DomainRegistry, build_default_registry
from .semantic import TypeEnv, infer, infer_block
from .optimizer import optimize_program
from .goal_ir import GoalIR, lower_goals, format_goal_ir
from .goal_plan import analyze_goals, build_execution_plan
from .stdlib.registry import get as get_stdlib_function
from .diagnostics import current_source_location, current_source_text, set_source_location, SourceSpan
from .ast import mark_source_span, mark_source_span_tree, source_span_of

UNIT_DIM = {
    "kg": (1,0,0), "m": (0,1,0), "m2": (0,2,0), "s": (0,0,1), "mps": (0,1,-1),
    "m3_per_kg_s2": (-1,3,-2), "mps2": (0,1,-2), "N": (1,1,-2),
}
UNIT_SCALE = {"kg":1.0,"m":1.0,"m2":1.0,"s":1.0,"mps":1.0,"m3_per_kg_s2":1.0,"mps2":1.0,"N":1.0}
DOMAIN_REGISTRY = None

TIME_UNITS = {"second":1.0,"seconds":1.0,"s":1.0,"minute":60.0,"minutes":60.0,"hour":3600.0,"hours":3600.0,"day":86400.0,"days":86400.0}

@dataclass(frozen=True)
class Quantity:
    value: float
    unit: str
    def dim(self): return UNIT_DIM[self.unit]
    def __str__(self): return f"{self.value:g} {self.unit}"

def dim_add(a,b): return tuple(x+y for x,y in zip(a,b))
def dim_sub(a,b): return tuple(x-y for x,y in zip(a,b))
def unit_for_dim(dim):
    for u,d in UNIT_DIM.items():
        if d==dim: return u
    return None

def qadd(a,b):
    if a.dim()!=b.dim(): raise TypeError(f"cannot add {a.unit} and {b.unit}")
    return Quantity(a.value+b.value,a.unit)
def qsub(a,b):
    if a.dim()!=b.dim(): raise TypeError(f"cannot subtract {a.unit} and {b.unit}")
    return Quantity(a.value-b.value,a.unit)
def qmul(a,b):
    if isinstance(a,(int,float)) and isinstance(b,(int,float)): return a*b
    if isinstance(a,(int,float)): return Quantity(a*b.value,b.unit)
    if isinstance(b,(int,float)): return Quantity(a.value*b,a.unit)
    u=unit_for_dim(dim_add(a.dim(),b.dim())) or f"<dim:{dim_add(a.dim(),b.dim())}>"
    return Quantity(a.value*b.value,u)
def qdiv(a,b):
    # Keep the same actionable message in the reference and planned runtimes.
    divisor = b if isinstance(b, (int, float)) else getattr(b, "value", None)
    if divisor == 0:
        raise ZeroDivisionError("division by zero: the divisor must be non-zero")
    if isinstance(a,(int,float)) and isinstance(b,(int,float)): return a/b
    if isinstance(b,(int,float)): return Quantity(a.value/b,a.unit)
    if isinstance(a,(int,float)) and isinstance(b,Quantity):
        u=unit_for_dim(tuple(-x for x in b.dim())) or f"<dim:{tuple(-x for x in b.dim())}>"
        return Quantity(a/b.value,u)
    u=unit_for_dim(dim_sub(a.dim(),b.dim())) or f"<dim:{dim_sub(a.dim(),b.dim())}>"
    return Quantity(a.value/b.value,u)

def pow2(q):
    dim=tuple(2*x for x in q.dim()); u=unit_for_dim(dim) or f"<dim:{dim}>"
    return Quantity(q.value*q.value,u)

@dataclass
class UserEntity:
    type_name: str
    name: str
    fields: dict[str, object]

class FunctionValue:
    """Runtime function value with a lexical closure.

    The closure is the defining scope, not the calling scope.  This makes
    higher-order functions deterministic: a function keeps access to the
    bindings that existed where it was created.
    """
    def __init__(self, decl, program, closure=None):
        self.decl = decl
        self.program = program
        self.closure = closure


    @property
    def name(self):
        return self.decl.name

    def __call__(self, args):
        if len(args) != len(self.decl.parameters):
            raise TypeError(f"function '{self.decl.name}' expects {len(self.decl.parameters)} argument(s), got {len(args)}")
        local = dict(self.closure or {})
        local.update({name: value for (name, _), value in zip(self.decl.parameters, args)})
        return _eval_block(self.decl.body, self.program, local=local)


class ComposedFunctionValue(FunctionValue):
    """Unary composition f(g(x)) as a first-class S-Lang function value."""
    def __init__(self, outer, inner):
        self.outer = outer
        self.inner = inner
        self.decl = None
        self.program = getattr(outer, "program", None)
        self.closure = None

    @property
    def name(self):
        return "compose"

    def __call__(self, args):
        if len(args) != 1:
            raise TypeError("composed function expects 1 argument")
        return self.outer([self.inner([args[0]])])


def _is_function_value(value):
    return isinstance(value, (FunctionValue, ComposedFunctionValue))


class RecordValue(dict):
    """Runtime record preserving its declared S-Lang record type."""
    def __init__(self, type_name: str | None, values: dict[str, object]):
        super().__init__(values)
        self.type_name = type_name

@dataclass
class Body:
    name: str
    fields: dict[str,Quantity]

@dataclass(frozen=True)
class DataRow:
    name: str
    age: int

@dataclass(frozen=True)
class Circle:
    name: str
    radius: Quantity

@dataclass(frozen=True)
class GraphPath:
    nodes: tuple[str, ...]
    cost: float

@dataclass
class Program:
    gravity: bool
    bodies: list[Body]
    simulation: tuple[str,str,float,float] | None
    shows: list[tuple[str,str]]
    show_exprs: list[object] = None
    people: list[DataRow] = None
    data_query: tuple[str,str,int,str] | None = None  # source, op, threshold, result name
    circles: list[Circle] = None
    ast: Module = None
    data_tables: dict[str, list[dict]] = None
    entities: dict[str, UserEntity] = None
    base_dir: object = None

class ParseError(Exception):
    """Parser error carrying a best-effort source location and stable code."""
    def __init__(self, message, *, line=None, column=None, end_column=None, code="E1000"):
        super().__init__(message)
        self.code = code
        location = current_source_location()
        if line is not None:
            from .diagnostics import SourceSpan
            self.span = SourceSpan.line(line, column or 1, end_column)
        else:
            self.span = location

def domain_registry():
    global DOMAIN_REGISTRY
    if DOMAIN_REGISTRY is None:
        DOMAIN_REGISTRY = build_default_registry(Quantity, quantity_type, entity_type, UNIT_DIM)
    return DOMAIN_REGISTRY

def register_domain(domain):
    """Register an external semantic domain without modifying the core compiler."""
    domain_registry().register(domain)


NUM_UNIT = re.compile(r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s+([A-Za-z0-9_]+)$")

def parse_quantity(text):
    m=NUM_UNIT.match(text.strip())
    if not m: raise ParseError(f"invalid quantity: {text}")
    value=float(m.group(1)); unit=m.group(2)
    if unit not in UNIT_DIM: raise ParseError(f"unknown unit '{unit}'")
    return Quantity(value,unit)

def parse_duration(num, word):
    if word not in TIME_UNITS: raise ParseError(f"unknown time unit '{word}'")
    return float(num)*TIME_UNITS[word]

def split_top_level(text, separator=','):
    out=[]; start=0; depth=0
    for i,ch in enumerate(text):
        if ch in '(<': depth+=1
        elif ch in ')>': depth-=1
        elif ch==separator and depth==0:
            out.append(text[start:i]); start=i+1
    out.append(text[start:])
    return out

_EXPR_TOKEN = re.compile(r"\s*(?:((?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)(?:\s+([A-Za-z][A-Za-z0-9_]*))?|([A-Za-z_][A-Za-z0-9_]*)|(\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*')|(>=|<=|==|!=|[+\-*/%^(),:.<>\[\]{}]))")

def _expr_tokens(text):
    pos=0; tokens=[]; spans=[]
    while pos < len(text):
        m=_EXPR_TOKEN.match(text,pos)
        if not m: raise ParseError(f"invalid expression near '{text[pos:]}'")
        start=m.start(); end=m.end()
        leading = len(m.group(0)) - len(m.group(0).lstrip())
        start += leading
        num,unit,name,string,op=m.groups(); pos=end
        if num is not None:
            if unit is not None and unit not in UNIT_DIM:
                unit_start=end-len(unit)
                tokens.append(('literal', num, None)); spans.append((start,unit_start))
                tokens.append(('name', unit)); spans.append((unit_start,end))
            else:
                tokens.append(('literal',num,unit)); spans.append((start,end))
        elif name is not None: tokens.append(('name',name)); spans.append((start,end))
        elif string is not None:
            quote=string[0]; raw=string[1:-1]
            try: value=bytes(raw, 'utf-8').decode('unicode_escape')
            except UnicodeDecodeError as exc: raise ParseError(f'invalid string literal: {exc}')
            tokens.append(('string', value)); spans.append((start,end))
        else: tokens.append((op,op)); spans.append((start,end))
    tokens.append(('EOF','EOF')); spans.append((len(text),len(text)))
    return tokens, spans

class _ExprParser:
    def __init__(self,text, span=None):
        self.text=text; self.t,self.ts=_expr_tokens(text); self.i=0; self.base_span=span
    def peek(self): return self.t[self.i][0]
    def pop(self): x=self.t[self.i]; self.i+=1; return x
    def accept(self,k):
        if self.peek()==k: return self.pop()
        return None
    def expect(self,k):
        x=self.accept(k)
        if x is None: raise ParseError(f"expected '{k}' in expression")
        return x
    def _span(self,start_i,end_i=None):
        if end_i is None: end_i=self.i-1
        if self.base_span is None or start_i >= len(self.ts): return None
        a=self.ts[start_i][0]; b=self.ts[min(end_i,len(self.ts)-1)][1]
        base=self.base_span.start
        return SourceSpan.range(base.line, base.column+a, base.line, base.column+b)
    def _mark(self,node,start_i,end_i=None):
        return mark_source_span(node,self._span(start_i,end_i))
    def parse(self):
        start=self.i; e=self.logical_or()
        if self.peek()!='EOF': raise ParseError(f"unexpected token '{self.t[self.i][1]}'")
        return self._mark(e,start,self.i-1)
    def logical_or(self):
        start=self.i; e=self.logical_and()
        while self.peek()=='name' and self.t[self.i][1]=='or':
            self.pop(); e=Logical('or', e, self.logical_and()); e=self._mark(e,start,self.i-1)
        return self._mark(e,start,self.i-1)
    def logical_and(self):
        start=self.i; e=self.compare()
        while self.peek()=='name' and self.t[self.i][1]=='and':
            self.pop(); e=Logical('and', e, self.compare()); e=self._mark(e,start,self.i-1)
        return self._mark(e,start,self.i-1)
    def compare(self):
        start=self.i; e=self.add()
        if self.peek() in ('>=','<=','==','!=','>','<'):
            op=self.pop()[0]; e=Compare(op,e,self.add())
            e=self._mark(e,start,self.i-1)
        return self._mark(e,start,self.i-1)
    def add(self):
        start=self.i; e=self.mul()
        while self.peek() in ('+','-'):
            op=self.pop()[0]; e=Binary(op,e,self.mul())
            e=self._mark(e,start,self.i-1)
        return self._mark(e,start,self.i-1)
    def mul(self):
        start=self.i; e=self.unary()
        while self.peek() in ('*','/','%'):
            op=self.pop()[0]; e=Binary(op,e,self.unary())
            e=self._mark(e,start,self.i-1)
        return self._mark(e,start,self.i-1)
    def unary(self):
        start=self.i
        if self.accept('+'):
            # Unary plus preserves the operand value while retaining a source span.
            e=self.unary()
            return self._mark(e,start,self.i-1)
        if self.accept('-'):
            # Represent unary negation with the existing, backend-supported binary node.
            e=Binary('-', Literal(0), self.unary())
            return self._mark(e,start,self.i-1)
        return self.pow()
    def pow(self):
        start=self.i; e=self.atom()
        if self.accept('^'):
            e=Binary('^',e,self.unary())
            e=self._mark(e,start,self.i-1)
        return self._mark(e,start,self.i-1)
    def atom(self):
        start=self.i
        if self.peek()=='name' and self.t[self.i][1]=='if':
            self.pop()
            condition = self.logical_or()
            token = self.pop()
            if token[0] != 'name' or token[1] != 'then':
                raise ParseError("expected 'then' in conditional expression")
            then_expr = self.logical_or()
            token = self.pop()
            if token[0] != 'name' or token[1] != 'else':
                raise ParseError("expected 'else' in conditional expression")
            return self._mark(Conditional(condition, then_expr, self.logical_or()), start, self.i - 1)
        if self.accept('{'):
            items = {}
            if self.peek() != '}':
                while True:
                    key = self.pop()
                    if key[0] not in ('name', 'string'):
                        raise ParseError('record keys must be names or Text literals')
                    self.expect(':')
                    items[key[1]] = self.logical_or()
                    if not self.accept(','):
                        break
            self.expect('}')
            return self._mark(Literal(items), start, self.i - 1)
        if self.accept('['):
            items=[]
            if self.peek()!=']':
                items.append(self.logical_or())
                while self.accept(','): items.append(self.logical_or())
            self.expect(']'); return self._mark(Literal(items),start,self.i-1)
        if self.peek()=='string':
            self.pop(); return self._mark(Literal(self.t[start][1]),start,self.i-1)
        if self.accept('('):
            e=self.logical_or(); self.expect(')'); return self._mark(e,start,self.i-1)
        if self.peek()=='name' and self.t[self.i][1]=='not':
            self.pop(); return self._mark(Logical('not', self.atom(), None),start,self.i-1)
        if self.peek()=='literal':
            _,num,unit=self.pop(); value=float(num)
            if value.is_integer(): value=int(value)
            if unit: value=parse_quantity(f'{num} {unit}')
            return self._mark(Literal(value),start,self.i-1)
        if self.peek()=='name':
            name=self.pop()[1]
            if name in ('true','false'):
                return self._mark(Literal(name == 'true'),start,self.i-1)
            parts=[]
            while self.accept('.'):
                parts.append(self.expect('name')[1])
            if self.accept('('):
                callable_name='.'.join([name, *parts]); args=[]
                if self.peek()!=')':
                    args.append(self.logical_or())
                    while self.accept(','): args.append(self.logical_or())
                self.expect(')')
                expr=self._mark(Call(callable_name,tuple(args)),start,self.i-1)
                while self.accept('.'):
                    part=self.expect('name')[1]; expr=self._mark(Property(expr,part),start,self.i-1)
                return expr
            expr=self._mark(Name(name),start,self.i-1)
            for part in parts:
                expr=self._mark(Property(expr,part),start,self.i-1)
            return expr
        raise ParseError(f"unexpected token '{self.t[self.i][1]}'")

def parse_expr(text):
    span = current_source_location()
    source_text = current_source_text()
    expr_text = text.strip()
    if span is not None and source_text is not None and expr_text:
        lines=source_text.splitlines()
        line_no=span.start.line-1
        if 0 <= line_no < len(lines):
            line=lines[line_no]
            start_at=max(0, span.start.column-1)
            offset=line.find(expr_text,start_at)
            if offset >= 0:
                span=SourceSpan.range(span.start.line, offset+1, span.start.line, offset+len(expr_text)+1)
    node = _ExprParser(expr_text, span).parse()
    return mark_source_span_tree(node, span)

def bind_row_expr(expr, outer_names=()):
    """Bind collection expressions to the current item while preserving lexical names."""
    span = source_span_of(expr)
    def finish(node):
        if span is not None and source_span_of(node) is None:
            return mark_source_span(node, span)
        return node
    outer_names = set(outer_names)
    if isinstance(expr, Name):
        if expr.name in ("row", "item", "acc") or expr.name in outer_names:
            return finish(Name(expr.name))
        return finish(Field(Name("row"), expr.name))
    if isinstance(expr, Literal): return finish(expr)
    if isinstance(expr, Field): return finish(Field(bind_row_expr(expr.base, outer_names), expr.name))
    if isinstance(expr, Property): return finish(Property(bind_row_expr(expr.base, outer_names), expr.name))
    if isinstance(expr, Binary): return finish(Binary(expr.op, bind_row_expr(expr.left, outer_names), bind_row_expr(expr.right, outer_names)))
    if isinstance(expr, Compare): return finish(Compare(expr.op, bind_row_expr(expr.left, outer_names), bind_row_expr(expr.right, outer_names)))
    if isinstance(expr, Logical): return finish(Logical(expr.op, bind_row_expr(expr.left, outer_names), bind_row_expr(expr.right, outer_names) if expr.right is not None else None))
    if isinstance(expr, Conditional): return finish(Conditional(bind_row_expr(expr.condition, outer_names), bind_row_expr(expr.then_expr, outer_names), bind_row_expr(expr.else_expr, outer_names)))
    if isinstance(expr, Call): return finish(Call(expr.name, tuple(bind_row_expr(a, outer_names) for a in expr.args)))
    return finish(expr)

def parse_type_ref(text):
    text = text.strip()
    m = re.fullmatch(r"([A-Za-z_]\w*)\s*<(.+)>", text)
    if m:
        name, inner = m.groups()
        args = tuple(parse_type_ref(part.strip()) for part in split_top_level(inner, ','))
        return TypeRef(name, args)
    aliases = {
        "Number": "Number", "Boolean": "Boolean", "Text": "Text",
        "kg": "kg", "m": "m", "s": "s", "mps": "mps", "m2": "m2",
        "mps2": "mps2", "N": "N", "m3_per_kg_s2": "m3_per_kg_s2", "Record": "Record",
        "List": "List", "Entity": "Entity",
    }
    return TypeRef(aliases.get(text, text))

def _indent(raw):
    return len(raw) - len(raw.lstrip(' \t'))

def _span_through_lines(start_span, lines, next_index):
    """Return a source range from a construct's first line through its last consumed line."""
    if start_span is None or next_index <= 0 or not lines:
        return start_span
    last_index = min(next_index - 1, len(lines) - 1)
    return SourceSpan.range(
        start_span.start.line,
        start_span.start.column,
        last_index + 1,
        len(lines[last_index]) + 1,
    )

def _next_nonblank_indent(lines, i):
    j=i
    while j < len(lines) and not lines[j].strip():
        j += 1
    return _indent(lines[j]) if j < len(lines) else None

def _parse_local_collection_statement(text):
    """Parse local collection statements and pipelines using canonical syntax."""
    declaration = re.fullmatch(r"let\s+(\w+)\s*=\s*(.+)", text)
    if not declaration:
        return None
    name, rhs = declaration.groups()
    if '|>' in rhs:
        parts = re.split(r"\s*\|>\s*", rhs)
        source = parts[0].strip()
        if not re.fullmatch(r"\w+", source):
            return None
        operations = parts[1:]
    else:
        simple = re.fullmatch(r"(\w+)\s+(.+)", rhs)
        if not simple:
            return None
        source, operation_text = simple.groups()
        operations = [operation_text]
    stages = []
    for part in operations:
        part = part.strip()
        sm = re.fullmatch(r"where\s+(.+)", part)
        mm = re.fullmatch(r"map\s+(.+)", part)
        so = re.fullmatch(r"sort\s+by\s+(.+?)(?:\s+(asc|desc))?", part)
        red = re.fullmatch(r"reduce\s+(.+?)\s+with\s+(.+)", part)
        agg = re.fullmatch(r"(sum|count|max|min|average|avg|any|all)(?:\s+(.+))?", part)
        if sm: stages.append(("where", parse_expr(sm.group(1)), None, None))
        elif mm: stages.append(("map", parse_expr(mm.group(1)), None, None))
        elif so: stages.append(("sort", parse_expr(so.group(1)), None, so.group(2) or "asc"))
        elif red: stages.append(("reduce", parse_expr(red.group(2)), parse_expr(red.group(1)), None))
        elif agg:
            op, expr = agg.groups()
            stages.append((op, parse_expr(expr) if expr else None, None, None))
        else:
            return None
    if not stages:
        return None
    return LocalCollectionOp(name, source, tuple(stages))

def parse_block(lines, i, owner, required_indent, *, allow_show=False, allow_return=True, allow_function=True):
    body=[]
    while i < len(lines):
        raw=lines[i]
        set_source_location(i + 1, max(1, len(raw) - len(raw.lstrip()) + 1), len(raw) + 1, raw)
        if not raw.strip():
            i += 1
            continue
        ind=_indent(raw)
        if ind < required_indent:
            break
        if ind > required_indent:
            raise ParseError(f"unexpected indentation in {owner}")
        bs=raw.strip()
        if bs == 'else:':
            break
        i += 1
        fm = re.fullmatch(r"function\s+(\w+)(?:\s*<([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)>)?\s*\((.*?)\)(?:\s*->\s*([A-Za-z_]\w*(?:\s*<.*>)?))?:", bs)
        if fm:
            if not allow_function:
                raise ParseError(f"nested function declarations are not allowed in {owner}")
            fname, type_params_text, params_text, ret_text = fm.groups()
            type_params = tuple(x.strip() for x in type_params_text.split(',')) if type_params_text else ()
            if len(set(type_params)) != len(type_params):
                raise ParseError(f"duplicate generic type parameter in function '{fname}'")
            params=[]
            if params_text.strip():
                for part in split_top_level(params_text, ','):
                    part = part.strip()
                    pm = re.fullmatch(r"(\w+)(?:\s*:\s*(.+))?", part)
                    if not pm: raise ParseError(f"invalid function parameter: {part}")
                    params.append((pm.group(1), parse_type_ref(pm.group(2)) if pm.group(2) else None))
            decl_span = current_source_location()
            child_indent=_next_nonblank_indent(lines, i)
            if child_indent is None or child_indent <= required_indent:
                raise ParseError(f"function '{fname}' requires an indented body")
            child_body, i = parse_block(lines, i, f"function '{fname}'", child_indent)
            if not child_body or not _returns_on_all_paths(child_body):
                raise ParseError(f"function '{fname}' must return on all control-flow paths")
            body.append(mark_source_span(FunctionDecl(fname, params, parse_type_ref(ret_text) if ret_text else None, child_body, type_params), _span_through_lines(decl_span, lines, i)))
            continue
        # Collection transformations are also valid local statements inside
        # functions and conditional blocks. Their result is scoped locally.
        local_collection = _parse_local_collection_statement(bs)
        if local_collection is not None:
            body.append(mark_source_span(local_collection, current_source_location()))
            continue
        lm=re.fullmatch(r"let\s+(\w+)\s*=\s*(.+)", bs)
        if lm:
            body.append(mark_source_span(LetOp(lm.group(1), parse_expr(lm.group(2))), current_source_location()))
            continue
        rm=re.fullmatch(r"return\s+(.+)", bs)
        if rm:
            if not allow_return:
                raise ParseError(f"return is only allowed inside functions and computed properties (line {i})")
            body.append(mark_source_span(ReturnOp(parse_expr(rm.group(1))), current_source_location()))
            continue
        im=re.fullmatch(r"if\s+(.+):", bs)
        if im:
            statement_span = current_source_location()
            condition=parse_expr(im.group(1))
            child_indent=_next_nonblank_indent(lines, i)
            if child_indent is None or child_indent <= required_indent:
                raise ParseError(f"if block requires an indented body in {owner}")
            then_body, i = parse_block(lines, i, owner, child_indent, allow_show=allow_show, allow_return=allow_return, allow_function=allow_function)
            if not then_body:
                raise ParseError(f"empty if block in {owner}")
            else_body=[]
            # else must be at the same indentation as the if.
            j=i
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and _indent(lines[j]) == required_indent and lines[j].strip() == 'else:':
                i=j+1
                else_indent=_next_nonblank_indent(lines, i)
                if else_indent is None or else_indent <= required_indent:
                    raise ParseError(f"else block requires an indented body in {owner}")
                else_body, i = parse_block(lines, i, owner, else_indent, allow_show=allow_show, allow_return=allow_return, allow_function=allow_function)
                if not else_body:
                    raise ParseError(f"empty else block in {owner}")
            body.append(mark_source_span(IfOp(condition, then_body, else_body), _span_through_lines(statement_span, lines, i)))
            continue
        sm = re.fullmatch(r"show\s+(.+)", bs)
        if sm and allow_show:
            for item in split_top_level(sm.group(1), ','):
                body.append(mark_source_span(ShowOp(parse_expr(item.strip())), current_source_location()))
            continue
        raise ParseError(f"invalid statement in {owner}: {bs}")
    return body, i

def _returns_on_all_paths(body):
    """Return True only when every reachable path through a block returns.

    A return inside one branch is not enough: the other branch (or the
    fall-through path) must also return.  This keeps function/property
    declarations total at the language level instead of discovering a
    missing return only at runtime.
    """
    for stmt in body:
        if isinstance(stmt, ReturnOp):
            return True
        if isinstance(stmt, IfOp):
            if stmt.else_body and _returns_on_all_paths(stmt.then_body) and _returns_on_all_paths(stmt.else_body):
                return True
            # An if without two returning branches can still be followed by
            # a later return, so continue analysing the enclosing block.
    return False

def _strip_line_comment(line: str) -> str:
    """Remove a trailing # comment while preserving hashes inside strings.

    Replacing the comment tail with spaces keeps source columns and indentation
    stable for diagnostics and block parsing.
    """
    quote = None
    escaped = False
    for index, char in enumerate(line):
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
        elif char == "#":
            return line[:index] + " " * (len(line) - index)
    return line


def parse(source, base_dir=None, _import_stack=None):
    """Parse S-Lang source, recursively resolving source-module imports."""
    from pathlib import Path
    base_dir = Path(base_dir) if base_dir is not None else None
    _import_stack = list(_import_stack or [])
    lines=[_strip_line_comment(line) for line in source.splitlines()]; i=0; module_decl=None; imports=[]; data_spans={}; circle_spans={}; sim_span=None; reexports=[]; module_exports_decl=() ; gravity=False; bodies=[]; sim=None; shows=[]; show_exprs=[]; people=[]; data_query=None; circles=[]; data_tables={}; entity_decls=[]; record_decls=[]; bindings=[]; states=[]; state_sets=[]; pending_filters=[]; pending_sorts=[]; pending_maps=[]; pending_aggregates=[]; pending_reduces=[]; pending_conditional_pipelines=[]; pending_sequences=[]; pending_goals=[]; pending_path_goals=[]; pending_satisfy_goals=[]; graphs=[]; functions=[]; properties=[]; ordered_effects=[]; top_level_statements=[]
    def visible_row_names():
        # Names declared before a collection operation are lexical values, not
        # implicit fields of the current row. Unknown bare names remain fields.
        return {item.name for item in bindings} | {item.name for item in states} | {item.name for item in functions}
    while i<len(lines):
        raw=lines[i]; s=raw.strip(); i+=1
        set_source_location(i, max(1, len(raw) - len(raw.lstrip()) + 1), len(raw) + 1, raw)
        if not s or s.startswith('#'): continue
        mm = re.fullmatch(r"module\s+([A-Za-z_][A-Za-z0-9_.-]*)", s)
        if mm:
            if module_decl is not None:
                raise ParseError("duplicate module declaration")
            module_decl = mark_source_span(ModuleDecl(mm.group(1)), current_source_location()); continue
        rem = re.fullmatch(r"export\s+(?:\{\s*)?([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)(?:\s*\})?\s+from\s+\"([^\"]+)\"", s)
        if rem:
            names = tuple(x.strip() for x in rem.group(1).split(','))
            reexports.append((rem.group(2), names))
            continue
        em = re.fullmatch(r"export\s+([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)", s)
        if em:
            if module_exports_decl:
                raise ParseError("duplicate export declaration")
            module_exports_decl = tuple(x.strip() for x in em.group(1).split(','))
            continue
        im = re.fullmatch(r'import\s+\"([^\"]+)\"(?:\s+as\s+([A-Za-z_][A-Za-z0-9_]*))?(?:\s+\{\s*([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)\s*\})?', s)
        if im:
            names = tuple(x.strip() for x in im.group(3).split(',')) if im.group(3) else ()
            imports.append(mark_source_span(ImportDecl(im.group(1), im.group(2), names), current_source_location())); continue
        im = re.fullmatch(r"import\s+(std\.[A-Za-z_][A-Za-z0-9_]*)(?:\s+as\s+([A-Za-z_][A-Za-z0-9_]*))?", s)
        if im:
            from .stdlib.modules import MODULES
            module_name = im.group(1).split(".", 1)[1]
            if module_name not in MODULES:
                raise ParseError(f"unknown standard-library module: '{im.group(1)}'")
            imports.append(mark_source_span(ImportDecl(im.group(1), im.group(2)), current_source_location())); continue
        im = re.fullmatch(r'import\s+([A-Za-z_][A-Za-z0-9_.-]*)(?:\s+as\s+([A-Za-z_][A-Za-z0-9_]*))?(?:\s+\{\s*([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)\s*\})?', s)
        if im and not im.group(1).startswith("std."):
            names = tuple(x.strip() for x in im.group(3).split(',')) if im.group(3) else ()
            imports.append(mark_source_span(ImportDecl(im.group(1), im.group(2), names), current_source_location())); continue
        top_if = re.fullmatch(r"if\s+(.+):", s)
        if top_if:
            statement_span = current_source_location()
            condition = parse_expr(top_if.group(1))
            body_indent = _next_nonblank_indent(lines, i)
            if body_indent is None or body_indent <= 0:
                raise ParseError("top-level if requires an indented body")
            then_body, i = parse_block(lines, i, "top-level if", body_indent, allow_show=True, allow_return=False, allow_function=False)
            if not then_body:
                raise ParseError("empty top-level if block")
            else_body = []
            j = i
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and _indent(lines[j]) == 0 and lines[j].strip() == "else:":
                i = j + 1
                else_indent = _next_nonblank_indent(lines, i)
                if else_indent is None or else_indent <= 0:
                    raise ParseError("top-level else requires an indented body")
                else_body, i = parse_block(lines, i, "top-level else", else_indent, allow_show=True, allow_return=False, allow_function=False)
                if not else_body:
                    raise ParseError("empty top-level else block")
            statement = mark_source_span(IfOp(condition, then_body, else_body), _span_through_lines(statement_span, lines, i))
            top_level_statements.append(statement)
            continue
        fm = re.fullmatch(r"function\s+(\w+)(?:\s*<([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)>)?\s*\((.*?)\)(?:\s*->\s*([A-Za-z_]\w*(?:\s*<.*>)?))?:", s)
        if fm:
            fname, type_params_text, params_text, ret_text = fm.groups()
            type_params = tuple(x.strip() for x in type_params_text.split(',')) if type_params_text else ()
            if len(set(type_params)) != len(type_params):
                raise ParseError(f"duplicate generic type parameter in function '{fname}'")
            params=[]
            if params_text.strip():
                for part in split_top_level(params_text, ','):
                    part = part.strip()
                    pm = re.fullmatch(r"(\w+)(?:\s*:\s*(.+))?", part)
                    if not pm: raise ParseError(f"invalid function parameter: {part}")
                    params.append((pm.group(1), parse_type_ref(pm.group(2)) if pm.group(2) else None))
            body_indent=_next_nonblank_indent(lines, i)
            if body_indent is None or body_indent <= 0: raise ParseError(f"function '{fname}' requires an indented body")
            decl_span = current_source_location()
            body, i = parse_block(lines, i, f"function '{fname}'", body_indent)
            if not body or not _returns_on_all_paths(body):
                raise ParseError(f"function '{fname}' must return on all control-flow paths")
            functions.append(mark_source_span(FunctionDecl(fname, params, parse_type_ref(ret_text) if ret_text else None, body, type_params), _span_through_lines(decl_span, lines, i)))
            continue
        pm = re.fullmatch(r"property\s+(\w+)\.(\w+)(?:\s*->\s*(\w+))?:", s)
        if pm:
            entity, pname, ret_text = pm.groups()
            body_indent=_next_nonblank_indent(lines, i)
            if body_indent is None or body_indent <= 0: raise ParseError(f"property '{entity}.{pname}' requires an indented body")
            decl_span = current_source_location()
            body, i = parse_block(lines, i, f"property '{entity}.{pname}'", body_indent)
            if not body or not _returns_on_all_paths(body):
                raise ParseError(f"property '{entity}.{pname}' must return on all control-flow paths")
            properties.append(mark_source_span(PropertyDecl(entity, pname, parse_type_ref(ret_text) if ret_text else None, body), _span_through_lines(decl_span, lines, i)))
            continue
        rm = re.fullmatch(r"record\s+(\w+)(?:\s*<([^>]+)>)?:", s)
        if rm:
            block_span_start = current_source_location()
            rname = rm.group(1); type_params=tuple(x.strip() for x in (rm.group(2) or '').split(',') if x.strip()); fields=[]; seen=set()
            if len(type_params) != len(set(type_params)): raise ParseError(f"duplicate generic parameter in record '{rname}'")
            if any(not re.fullmatch(r'[A-Z]\w*', x) for x in type_params): raise ParseError(f"invalid generic parameter in record '{rname}'")
            while i < len(lines) and (not lines[i].strip() or lines[i].startswith((' ','\t'))):
                rs = lines[i].strip(); i += 1
                if not rs: continue
                fm = re.fullmatch(r"(\w+)\s*:\s*([A-Za-z_]\w*(?:\s*<.*>)?)", rs)
                if not fm: raise ParseError(f"invalid record field: {rs}")
                fname, ftype = fm.groups()
                if fname in seen: raise ParseError(f"duplicate field '{fname}' in record '{rname}'")
                seen.add(fname); fields.append((fname, parse_type_ref(ftype)))
            if not fields: raise ParseError(f"record '{rname}' requires fields")
            record_decls.append(mark_source_span(RecordDecl(rname, fields, type_params), _span_through_lines(block_span_start, lines, i))); continue
        em = re.fullmatch(r"entity\s+(\w+):", s)
        if em:
            block_span_start = current_source_location()
            ename = em.group(1); fields=[]; seen=set()
            while i < len(lines) and (not lines[i].strip() or lines[i].startswith((' ','\t'))):
                es = lines[i].strip(); i += 1
                if not es: continue
                fm = re.fullmatch(r"(\w+)\s*:\s*([A-Za-z_]\w*(?:\s*<.*>)?)", es)
                if not fm: raise ParseError(f"invalid entity field: {es}")
                fname, ftype = fm.groups()
                if fname in seen: raise ParseError(f"duplicate field '{fname}' in entity '{ename}'")
                seen.add(fname); fields.append((fname, parse_type_ref(ftype)))
            if not fields: raise ParseError(f"entity '{ename}' requires fields")
            entity_decls.append(mark_source_span(EntityDecl(ename, fields), _span_through_lines(block_span_start, lines, i))); continue
        sm = re.fullmatch(r"state\s+(\w+)\s*=\s*(.+)", s)
        if sm:
            obj=mark_source_span(StateDecl(sm.group(1), parse_expr(sm.group(2))), current_source_location()); states.append(obj); ordered_effects.append(obj); continue
        stm = re.fullmatch(r"set\s+(\w+)\s*=\s*(.+)", s)
        if stm:
            obj=mark_source_span(SetStateOp(stm.group(1), parse_expr(stm.group(2))), current_source_location()); state_sets.append(obj); ordered_effects.append(obj); continue
        # Collection transformations are statements in the current AST, not
        # ordinary expressions. Accept the same forms with `let` as with the
        # legacy bare-assignment syntax so declarations are consistent.
        collection_let = re.fullmatch(r"let\s+(\w+)\s*=\s*(\w+)\s+(where|map|sum|count|max|min|average|avg|any|all)(?:\s+(.+))?", s)
        if collection_let:
            result, source, operation, expression_text = collection_let.groups()
            if operation == "where":
                if not expression_text:
                    raise ParseError("where requires a predicate")
                predicate = bind_row_expr(parse_expr(expression_text), visible_row_names())
                pending_filters.append(mark_source_span(FilterOp(source, Predicate(predicate), result), current_source_location()))
            elif operation == "map":
                if not expression_text:
                    raise ParseError("map requires an expression")
                pending_maps.append(mark_source_span(MapOp(source, bind_row_expr(parse_expr(expression_text), visible_row_names()), result), current_source_location()))
            else:
                if operation == "count":
                    expr = Literal(1)
                elif not expression_text:
                    expr = Name("item")
                else:
                    expr = bind_row_expr(parse_expr(expression_text), visible_row_names())
                pending_aggregates.append(mark_source_span(AggregateOp(source, operation, expr, result), current_source_location()))
            continue
        collection_reduce_let = re.fullmatch(r"let\s+(\w+)\s*=\s*(\w+)\s+reduce\s+(.+?)\s+with\s+(.+)", s)
        if collection_reduce_let:
            result, source, initial_text, expression_text = collection_reduce_let.groups()
            initial = parse_expr(initial_text)
            step_expr = bind_row_expr(parse_expr(expression_text), visible_row_names())
            if isinstance(initial, Literal) and isinstance(initial.value, bool) and isinstance(step_expr, Logical) and step_expr.op in {"and", "or"} and isinstance(step_expr.left, Name) and step_expr.left.name == "acc":
                pending_aggregates.append(mark_source_span(AggregateOp(source, "all" if step_expr.op == "and" else "any", step_expr.right, result), current_source_location()))
            else:
                pending_reduces.append(mark_source_span(ReduceOp(source, initial, step_expr, result), current_source_location()))
            continue
        lm = re.fullmatch(r"let\s+(\w+)\s*=\s*(\w+\s*\(.*\))", s)
        if lm:
            obj=mark_source_span(BindingDecl(lm.group(1), parse_expr(lm.group(2))), current_source_location()); bindings.append(obj); ordered_effects.append(obj); continue
        # `let` is the canonical declaration form. Keep declarative collection
        # statements out of the generic expression parser so `let result = ...`
        # works consistently for filters/maps/aggregates, sort, and pipelines.
        lm = re.fullmatch(r"let\s+(\w+)\s*=\s*(?!.*\|>)(?!.*\s+sort\s+by\s+)(.+)", s)
        if lm:
            obj=mark_source_span(BindingDecl(lm.group(1), parse_expr(lm.group(2))), current_source_location()); bindings.append(obj); ordered_effects.append(obj); continue
        cm = re.fullmatch(r"(\w+)\s*=\s*(\w+)\s*\((.*)\)", s)
        if cm:
            obj=mark_source_span(BindingDecl(cm.group(1), parse_expr(f"{cm.group(2)}({cm.group(3)})")), current_source_location()); bindings.append(obj); ordered_effects.append(obj); continue
        if s=="physics gravity": gravity=True; continue
        m=re.fullmatch(r"body\s+(\w+):",s)
        if m:
            block_span_start = current_source_location()
            name=m.group(1); fields={}
            while i<len(lines) and (not lines[i].strip() or lines[i].startswith((' ','\t'))):
                fs=lines[i].strip(); i+=1
                if not fs: continue
                fm=re.fullmatch(r"(\w+)\s+(.+)",fs)
                if not fm: raise ParseError(f"invalid body field: {fs}")
                fields[fm.group(1)]=parse_quantity(fm.group(2))
            bodies.append(mark_source_span(Body(name,fields), _span_through_lines(block_span_start, lines, i))); continue
        m=re.fullmatch(r"data\s+(\w+):",s)
        if m:
            block_span_start = current_source_location()
            dataset=m.group(1)
            rows=[]
            while i<len(lines) and (not lines[i].strip() or lines[i].startswith((' ','\t'))):
                ds=lines[i].strip(); i+=1
                if not ds: continue
                parts=ds.split()
                if len(parts)<3 or len(parts)%2==0: raise ParseError(f"invalid data row: {ds}")
                row={"name":parts[0]}
                for j in range(1,len(parts),2):
                    key,val=parts[j],parts[j+1]
                    if re.fullmatch(r"[+-]?\d+",val): value=int(val)
                    elif re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)",val): value=float(val)
                    else: value=val
                    row[key]=value
                rows.append(row)
                if dataset=="people" and "age" in row and isinstance(row["age"],int): people.append(DataRow(row["name"],row["age"]))
            data_tables[dataset]=rows; data_spans[dataset]=_span_through_lines(block_span_start, lines, i)
            continue
        # Compact declarative pipeline. Each stage lowers to the same
        # semantic operations used by the expanded syntax, so pipelines do
        # not introduce a second execution model.
        m=re.fullmatch(r"(?:let\s+)?(\w+)\s*=\s*(\w+)\s*\|>\s*(.+)",s)
        if m:
            final_result, source, pipeline_text = m.groups()

            def split_pipeline_stages(text):
                """Split '|>' only at the pipeline's top level.

                Parentheses are used to delimit conditional branches when a
                conditional stage is followed by an outer pipeline stage.
                """
                parts=[]; start_pos=0; depth=0; i2=0
                while i2 < len(text)-1:
                    ch=text[i2]
                    if ch == '(':
                        depth += 1
                    elif ch == ')' and depth:
                        depth -= 1
                    if depth == 0 and text[i2:i2+2] == '|>':
                        parts.append(text[start_pos:i2].strip())
                        start_pos=i2+2
                        i2 += 2
                        continue
                    i2 += 1
                parts.append(text[start_pos:].strip())
                return [x for x in parts if x]

            def implicit_pipeline_expr(text):
                """Expand compact expressions relative to the current item.

                Inside a pipeline, ``.field`` means ``item.field`` and a
                leading binary operator means that the left operand is the
                current item. This keeps common pipelines compact without
                introducing a second expression language.
                """
                text=text.strip()
                if text.startswith('.') and len(text) > 1:
                    return 'item' + text
                if re.match(r'^(>=|<=|==|!=|>|<|\*|/|%|\+|-)\s+', text):
                    return 'item ' + text
                if re.fullmatch(r'[A-Za-z_]\w*', text) and any(fn.name == text for fn in functions):
                    return text
                return text

            def pipeline_expr(text):
                text = text.strip()
                function_names = {fn.name for fn in functions}
                lexical_names = visible_row_names()
                # Track function-valued aliases, including higher-order
                # expressions such as compose(...), to prevent pipeline
                # shorthand from rewriting them into row fields.
                changed = True
                while changed:
                    changed = False
                    for binding in bindings:
                        expr = binding.expr
                        is_function_value = (
                            isinstance(expr, Name) and expr.name in function_names
                        ) or (
                            isinstance(expr, Call) and expr.name in {"compose"}
                        )
                        if is_function_value and binding.name not in function_names:
                            function_names.add(binding.name)
                            changed = True

                # Pipeline expressions use the current element as their
                # implicit input, but function-valued names must remain
                # values.  This is especially important for higher-order
                # composition such as `map compose(double, increment)`:
                # the function names are arguments to compose, not fields of
                # the current row.
                def bind_pipeline(node):
                    span = source_span_of(node)

                    def finish(value):
                        return mark_source_span_tree(value, span)

                    if isinstance(node, Name):
                        if node.name in ("row", "item", "acc") or node.name in function_names or node.name in lexical_names:
                            return finish(node)
                        return finish(Field(Name("row"), node.name))
                    if isinstance(node, Literal):
                        return finish(node)
                    if isinstance(node, Field):
                        return finish(Field(bind_pipeline(node.base), node.name))
                    if isinstance(node, Property):
                        return finish(Property(bind_pipeline(node.base), node.name))
                    if isinstance(node, Binary):
                        return finish(Binary(node.op, bind_pipeline(node.left), bind_pipeline(node.right)))
                    if isinstance(node, Compare):
                        return finish(Compare(node.op, bind_pipeline(node.left), bind_pipeline(node.right)))
                    if isinstance(node, Logical):
                        return finish(Logical(node.op, bind_pipeline(node.left), bind_pipeline(node.right) if node.right is not None else None))
                    if isinstance(node, Conditional):
                        return finish(Conditional(bind_pipeline(node.condition), bind_pipeline(node.then_expr), bind_pipeline(node.else_expr)))
                    if isinstance(node, Call):
                        return finish(Call(node.name, tuple(bind_pipeline(a) for a in node.args)))
                    return finish(node)


                parsed = parse_expr(implicit_pipeline_expr(text))
                return bind_pipeline(parsed)

            def parse_pipeline_stage(stage):
                wm=re.fullmatch(r"where\s+(.+)", stage)
                if wm:
                    return 'where', Predicate(pipeline_expr(wm.group(1)))
                sm=re.fullmatch(r"sort\s+by\s+(.+?)(?:\s+(asc|desc))?", stage)
                if sm:
                    expr_text,direction=sm.groups()
                    return 'sort', SortSpec(pipeline_expr(expr_text), direction != 'desc')
                mm2=re.fullmatch(r"map\s+(.+)", stage)
                if mm2:
                    return 'map', pipeline_expr(mm2.group(1))
                am=re.fullmatch(r"(sum|count|max|min|average|avg|any|all)(?:\s+(.+))?", stage)
                if am:
                    op,expr_text=am.groups()
                    if op == 'count': expr=Literal(1)
                    elif not expr_text: expr=Name('item')
                    else: expr=pipeline_expr(expr_text)
                    return 'aggregate', (op, expr)
                rm=re.fullmatch(r"reduce\s+(.+?)\s+with\s+(.+)", stage)
                if rm:
                    initial_text, expr_text=rm.groups()
                    return 'reduce', (parse_expr(initial_text), bind_row_expr(parse_expr(expr_text), visible_row_names()))
                raise ParseError(f"unknown pipeline stage: {stage}")

            def strip_balanced_outer_parens(text):
                text=text.strip()
                if not (text.startswith('(') and text.endswith(')')):
                    return None
                depth=0
                for pos,ch in enumerate(text):
                    if ch == '(':
                        depth += 1
                    elif ch == ')':
                        depth -= 1
                        if depth == 0 and pos != len(text)-1:
                            return None
                return text[1:-1].strip() if depth == 0 else None

            def split_top_level_keyword(text, keyword, start_at=0):
                depth=0; token=f" {keyword} "
                pos=start_at
                while pos <= len(text)-len(token):
                    ch=text[pos]
                    if ch == '(':
                        depth += 1
                    elif ch == ')' and depth:
                        depth -= 1
                    if depth == 0 and text.startswith(token,pos):
                        return pos
                    pos += 1
                return -1

            def parse_conditional_stage(text):
                if not text.startswith('if '):
                    raise ParseError("invalid conditional pipeline stage")
                then_pos=split_top_level_keyword(text, 'then', 2)
                if then_pos < 0:
                    raise ParseError("invalid conditional pipeline; expected 'if <condition> then <pipeline> else <pipeline>'")
                condition_text=text[3:then_pos].strip()
                after_then=text[then_pos+6:].strip()
                else_pos=split_top_level_keyword(after_then, 'else', 0)
                if else_pos < 0:
                    raise ParseError("invalid conditional pipeline; expected 'if <condition> then <pipeline> else <pipeline>'")
                then_text=after_then[:else_pos].strip()
                else_text=after_then[else_pos+6:].strip()

                # Parenthesized branches are required when the conditional is
                # followed by another outer '|>' stage. This removes the
                # otherwise unavoidable ambiguity between a branch-internal
                # '|>' and the outer continuation.
                then_inner=strip_balanced_outer_parens(then_text)
                else_inner=strip_balanced_outer_parens(else_text)
                if then_inner is not None and else_inner is not None:
                    then_parts=split_pipeline_stages(then_inner)
                    else_parts=split_pipeline_stages(else_inner)
                else:
                    # Backward-compatible form: an unparenthesized conditional
                    # may be used as the final pipeline construct on the line.
                    then_parts=split_pipeline_stages(then_text)
                    else_parts=split_pipeline_stages(else_text)
                if not then_parts or not else_parts:
                    raise ParseError("conditional pipeline branches require at least one stage")
                then_stages=tuple(parse_pipeline_stage(x) for x in then_parts)
                else_stages=tuple(parse_pipeline_stage(x) for x in else_parts)
                return parse_expr(condition_text), then_stages, else_stages

            # Preserve the original unparenthesized conditional syntax when
            # the conditional is the final pipeline construct. In that form
            # the branch chains are intentionally consumed as one construct.
            if pipeline_text.startswith('if ') and ' then (' not in pipeline_text:
                stages=[pipeline_text]
            else:
                stages=split_pipeline_stages(pipeline_text)
            if not stages:
                raise ParseError("pipeline requires at least one stage")
            pipeline_line = current_source_location()
            pipeline_source = current_source_text()
            line_text = None
            if pipeline_source is not None and pipeline_line is not None:
                source_lines = pipeline_source.splitlines()
                if 0 <= pipeline_line.start.line - 1 < len(source_lines):
                    line_text = source_lines[pipeline_line.start.line - 1]
            pipeline_abs = line_text.find(pipeline_text, max(0, pipeline_line.start.column - 1)) if line_text is not None else -1
            stage_spans=[]
            cursor=0
            for stage in stages:
                found=pipeline_text.find(stage, cursor)
                if pipeline_abs >= 0 and found >= 0:
                    stage_spans.append(SourceSpan.range(pipeline_line.start.line, pipeline_abs + found + 1, pipeline_line.start.line, pipeline_abs + found + len(stage) + 1))
                    cursor=found + len(stage)
                else:
                    stage_spans.append(pipeline_line)
            current=source
            for idx, stage in enumerate(stages):
                stage_span = stage_spans[idx]
                result = final_result if idx == len(stages)-1 else f"__pipe_{i}_{idx}"
                if stage.startswith('if '):
                    condition, then_stages, else_stages=parse_conditional_stage(stage)
                    pending_conditional_pipelines.append(mark_source_span(ConditionalPipelineOp(
                        current, condition, then_stages, else_stages, result), stage_span))
                    current=result
                    continue
                wm=re.fullmatch(r"where\s+(.+)", stage)
                if wm:
                    pending_filters.append(mark_source_span(FilterOp(current, Predicate(pipeline_expr(wm.group(1))), result), stage_span))
                    current=result; continue
                sm=re.fullmatch(r"sort\s+by\s+(.+?)(?:\s+(asc|desc))?", stage)
                if sm:
                    expr_text,direction=sm.groups()
                    pending_sorts.append(mark_source_span(SortOp(current, SortSpec(pipeline_expr(expr_text), direction != 'desc'), result), stage_span))
                    current=result; continue
                tm=re.fullmatch(r"tee\s+(\w+)", stage)
                if tm:
                    if idx == len(stages) - 1:
                        raise ParseError("pipeline 'tee' must be followed by another stage")
                    alias = tm.group(1)
                    if alias == current:
                        raise ParseError("pipeline 'tee' target must differ from its source")
                    pending_maps.append(mark_source_span(MapOp(current, bind_row_expr(Name("item"), visible_row_names()), alias), stage_span))
                    continue
                mm2=re.fullmatch(r"map\s+(.+)", stage)
                if mm2:
                    pending_maps.append(mark_source_span(MapOp(current, pipeline_expr(mm2.group(1)), result), stage_span))
                    current=result; continue
                am=re.fullmatch(r"(sum|count|max|min|average|avg|any|all)(?:\s+(.+))?", stage)
                if am:
                    op,expr_text=am.groups()
                    if op == 'count': expr=Literal(1)
                    elif not expr_text: expr=Name('item')
                    else: expr=pipeline_expr(expr_text)
                    pending_aggregates.append(mark_source_span(AggregateOp(current, op, expr, result), stage_span))
                    current=result; continue
                rm=re.fullmatch(r"reduce\s+(.+?)\s+with\s+(.+)", stage)
                if rm:
                    initial_text, expr_text=rm.groups()
                    initial_expr = parse_expr(initial_text)
                    step_expr = bind_row_expr(parse_expr(expr_text), visible_row_names())
                    if isinstance(initial_expr, Literal) and isinstance(initial_expr.value, bool) and isinstance(step_expr, Logical) and step_expr.op in {"and", "or"} and isinstance(step_expr.left, Name) and step_expr.left.name == "acc":
                        pending_aggregates.append(mark_source_span(AggregateOp(current, "all" if step_expr.op == "and" else "any", step_expr.right, result), stage_span))
                    else:
                        pending_reduces.append(mark_source_span(ReduceOp(current, initial_expr, step_expr, result), stage_span))
                    current=result; continue
                raise ParseError(f"unknown pipeline stage: {stage}")
            continue
        m=re.fullmatch(r"(\w+)\s*=\s*(\w+)\s+where\s+(.+)",s)
        if m:
            result,query_source,predicate_text=m.groups()
            predicate=bind_row_expr(parse_expr(predicate_text), visible_row_names())
            mod_filter=FilterOp(query_source,Predicate(predicate),result)
            # Keep the legacy field for compatibility with older callers; the
            # AST operation above is now the authoritative representation.
            data_query=(query_source,"generic",None,result)
            # Store temporarily; Module is constructed after the scan.
            if 'pending_filters' not in locals(): pending_filters=[]
            pending_filters.append(mark_source_span(mod_filter, current_source_location()))
            continue
        m=re.fullmatch(r"(?:(?:let\s+)?(\w+)\s*=\s*)?(\w+)\s+sort\s+by\s+(.+)",s)
        if m:
            assigned,source,sort_text=m.groups()
            result=assigned or source
            direction="asc"
            md=re.fullmatch(r"(.+?)\s+(asc|desc)",sort_text)
            if md:
                sort_text,direction=md.groups()
            if 'pending_sorts' not in locals(): pending_sorts=[]
            pending_sorts.append(mark_source_span(SortOp(source,SortSpec(bind_row_expr(parse_expr(sort_text), visible_row_names()),direction=="asc"),result), current_source_location()))
            continue
        m=re.fullmatch(r"(\w+)\s*=\s*(\w+)\s+map\s+(.+)",s)
        if m:
            result,source,expr_text=m.groups()
            pending_maps.append(mark_source_span(MapOp(source,bind_row_expr(parse_expr(expr_text), visible_row_names()),result), current_source_location()))
            continue
        m=re.fullmatch(r"(\w+)\s*=\s*(\w+)\s+(sum|count|max|min|average|avg|any|all)(?:\s+(.+))?",s)
        if m:
            result,source,op,expr_text=m.groups()
            if op == "count":
                expr = Literal(1)
            elif not expr_text:
                # Scalar collections may use the current item implicitly,
                # matching the concise pipeline-stage form.
                expr = Name("item")
            else:
                expr = bind_row_expr(parse_expr(expr_text), visible_row_names())
            pending_aggregates.append(mark_source_span(AggregateOp(source,op,expr,result), current_source_location()))
            continue
        m=re.fullmatch(r"(\w+)\s*=\s*(\w+)\s+reduce\s+(.+?)\s+with\s+(.+)",s)
        if m:
            result,source,initial_text,expr_text=m.groups()
            # The accumulator and current item are explicit semantic bindings.
            initial=parse_expr(initial_text)
            expr=parse_expr(expr_text)
            step_expr = bind_row_expr(expr, visible_row_names())
            if isinstance(initial, Literal) and isinstance(initial.value, bool) and isinstance(step_expr, Logical) and step_expr.op in {"and", "or"} and isinstance(step_expr.left, Name) and step_expr.left.name == "acc":
                pending_aggregates.append(AggregateOp(source, "all" if step_expr.op == "and" else "any", step_expr.right, result))
            else:
                pending_reduces.append(mark_source_span(ReduceOp(source,initial,step_expr,result), current_source_location()))
            continue
        m=re.fullmatch(r"sequence\s+(\w+)\s+from\s+(.+?)\s+for\s+(\d+)\s+steps\s+using\s+(.+)",s)
        if m:
            result,initial_text,steps_text,expr_text=m.groups()
            steps=int(steps_text)
            if steps <= 0:
                raise ParseError("sequence steps must be positive")
            initial=parse_expr(initial_text)
            expr=parse_expr(expr_text)
            # `value` is the current state; the expression computes the next state.
            pending_sequences.append(mark_source_span(SequenceOp(result,initial,steps,expr), current_source_location()))
            continue
        m=re.fullmatch(r"sequence\s+(\w+)\s+from\s+(.+?)\s+for\s+up\s+to\s+(\d+)\s+steps\s+until\s+(.+?)\s+using\s+(.+)",s)
        if m:
            result,initial_text,steps_text,until_text,expr_text=m.groups()
            steps=int(steps_text)
            if steps <= 0:
                raise ParseError("sequence maximum steps must be positive")
            initial=parse_expr(initial_text)
            until=parse_expr(until_text)
            expr=parse_expr(expr_text)
            pending_sequences.append(mark_source_span(SequenceOp(result,initial,steps,expr,until), current_source_location()))
            continue
        m=re.fullmatch(r"sequence\s+(\w+)\s+from\s+(.+?)\s+for\s+up\s+to\s+(\d+)\s+steps\s+toward\s+(.+?)\s+choosing:",s)
        if m:
            result,initial_text,steps_text,target_text=m.groups()
            steps=int(steps_text)
            if steps <= 0:
                raise ParseError("sequence maximum steps must be positive")
            body_indent=_next_nonblank_indent(lines, i)
            if body_indent is None or body_indent <= 0:
                raise ParseError(f"sequence '{result}' choosing requires an indented candidate block")
            candidates=[]
            constraints=[]
            while i < len(lines):
                raw_line=lines[i]
                if not raw_line.strip(): i += 1; continue
                indent=len(raw_line)-len(raw_line.lstrip(' \t'))
                if indent < body_indent: break
                if indent > body_indent: raise ParseError(f"invalid indentation in sequence '{result}' choosing")
                text=raw_line.strip()
                if text.startswith("satisfy "):
                    constraints.append(parse_expr(text[len("satisfy "):].strip()))
                else:
                    candidates.append(parse_expr(text))
                i += 1
            if len(candidates) < 2:
                raise ParseError(f"sequence '{result}' choosing requires at least two candidates")
            pending_sequences.append(mark_source_span(SequenceOp(result,parse_expr(initial_text),steps,Literal(None),None,parse_expr(target_text),tuple(candidates),constraints[0] if constraints else None,tuple(constraints)), current_source_location()))
            continue
        m=re.fullmatch(r"(\w+)\s*=\s*choose\s+(\w+)\s+from\s+(\w+)(?:\s+where\s+(.+?))?\s+(minimizing|maximizing)\s+(.+)",s)
        if m:
            result,_,source,predicate_text,direction,key_text=m.groups()
            predicate = Predicate(bind_row_expr(parse_expr(predicate_text), visible_row_names())) if predicate_text else None
            key = bind_row_expr(parse_expr(key_text), visible_row_names())
            pending_goals.append(mark_source_span(GoalOp(result, source, predicate, key, direction), current_source_location()))
            continue
        m=re.fullmatch(r"graph\s+(\w+):",s)
        if m:
            block_span_start = current_source_location()
            gname=m.group(1); edges=[]
            while i<len(lines) and (not lines[i].strip() or lines[i].startswith((' ','\t'))):
                gs=lines[i].strip(); i+=1
                if not gs: continue
                em=re.fullmatch(r"(\w+)\s*(<->|->)\s*(\w+)\s+cost\s+([0-9]+(?:\.[0-9]+)?)",gs)
                if not em: raise ParseError(f"invalid graph edge: {gs}")
                a,d,b,cost=em.groups(); cost=float(cost)
                if cost < 0: raise ParseError("graph edge cost must be non-negative")
                edges.append((a,b,cost,d=='<->'))
            if not edges: raise ParseError(f"graph '{gname}' requires edges")
            graphs.append(mark_source_span(GraphDecl(gname,edges), _span_through_lines(block_span_start, lines, i))); continue
        m=re.fullmatch(r"(\w+)\s*=\s*find\s+path\s+from\s+(\w+)\s+to\s+(\w+)\s+in\s+(\w+)\s+minimizing\s+cost",s)
        if m:
            result,start,end,source=m.groups()
            pending_path_goals.append(mark_source_span(PathGoalOp(result,source,start,end,'cost'), current_source_location())); continue
        m=re.fullmatch(r"(\w+)\s*=\s*satisfy:",s)
        if m:
            block_span_start = current_source_location()
            result=m.group(1); body_indent=_next_nonblank_indent(lines, i)
            if body_indent is None or body_indent <= 0:
                raise ParseError(f"satisfy '{result}' requires an indented block")
            variables=[]; constraints=[]
            while i < len(lines):
                raw_line=lines[i]
                if not raw_line.strip(): i += 1; continue
                indent=len(raw_line)-len(raw_line.lstrip(' \t'))
                if indent < body_indent: break
                if indent > body_indent: raise ParseError(f"invalid indentation in satisfy '{result}'")
                cs=raw_line.strip(); i += 1
                vm=re.fullmatch(r"(\w+)\s+in\s+(-?\d+)\.\.(-?\d+)", cs)
                if vm:
                    name,lo,hi=vm.groups(); lo=int(lo); hi=int(hi)
                    if lo > hi: raise ParseError(f"satisfy range for '{name}' must have lower <= upper")
                    if any(v[0]==name for v in variables): raise ParseError(f"duplicate satisfy variable '{name}'")
                    variables.append((name,lo,hi)); continue
                if not variables:
                    raise ParseError(f"satisfy '{result}' requires variable declarations before constraints")
                constraints.append(parse_expr(cs))
            if not variables: raise ParseError(f"satisfy '{result}' requires at least one variable")
            if not constraints: raise ParseError(f"satisfy '{result}' requires at least one constraint")
            pending_satisfy_goals.append(mark_source_span(SatisfyGoalOp(result, tuple(variables), tuple(constraints)), _span_through_lines(block_span_start, lines, i)))
            continue
        m=re.fullmatch(r"circle\s+(\w+):",s)
        if m:
            block_span_start = current_source_location()
            name=m.group(1); radius=None
            while i<len(lines) and (not lines[i].strip() or lines[i].startswith((' ','\t'))):
                cs=lines[i].strip(); i+=1
                if not cs: continue
                cm=re.fullmatch(r"radius\s+(.+)",cs)
                if cm: radius=parse_quantity(cm.group(1)); continue
                cm=re.fullmatch(r"center\s+(.+)",cs)
                if cm: continue
                raise ParseError(f"invalid circle field: {cs}")
            if radius is None: raise ParseError(f"circle {name} requires radius")
            circles.append(mark_source_span(Circle(name,radius), _span_through_lines(block_span_start, lines, i))); continue
        m=re.fullmatch(r"simulate\s+(\w+)\s+around\s+(\w+)\s+for\s+([0-9.]+)\s+(\w+)\s+step\s+([0-9.]+)\s+(\w+)",s)
        if m:
            sim=(m.group(1),m.group(2),parse_duration(m.group(3),m.group(4)),parse_duration(m.group(5),m.group(6))); sim_span=current_source_location(); continue
        m=re.fullmatch(r"show\s+(.+)",s)
        if m:
            for item in split_top_level(m.group(1), ','):
                expr=parse_expr(item.strip())
                show_exprs.append(expr)
                if isinstance(expr, Name): shows.append((expr.name,"__value__"))
                elif isinstance(expr, Property) and isinstance(expr.base, Name): shows.append((expr.base.name,expr.name))
                show_op = ShowOp(expr)
                ordered_effects.append(show_op)
                top_level_statements.append(show_op)
            continue
        raise ParseError(f"unknown syntax on line {i}: {s}")
    mod=Module(module=module_decl, imports=imports, gravity=gravity, exports=module_exports_decl, reexports=reexports)
    mod.module_exports = {}
    mod.bodies=[mark_source_span(BodyDecl(b.name,dict(b.fields)), source_span_of(b)) for b in bodies]
    # Dataset rows were already parsed above; reuse that representation for the
    # semantic AST instead of reparsing the source with a second regex grammar.
    for name, rows in data_tables.items():
        mod.datasets.append(mark_source_span(DataDecl(name, rows), data_spans.get(name)))
    mod.circles=[mark_source_span(CircleDecl(c.name,{"radius":c.radius}), source_span_of(c)) for c in circles]
    mod.filters.extend(pending_filters)
    mod.sorts.extend(pending_sorts)
    mod.maps.extend(pending_maps)
    mod.aggregates.extend(pending_aggregates)
    mod.conditional_pipelines.extend(pending_conditional_pipelines)
    mod.reduces.extend(pending_reduces)
    mod.sequences.extend(pending_sequences)
    mod.goals.extend(pending_goals)
    mod.graphs.extend(graphs)
    mod.path_goals.extend(pending_path_goals)
    mod.satisfy_goals.extend(pending_satisfy_goals)
    if sim:
        mod.simulations.append(mark_source_span(SimulationOp(*sim), sim_span))
    mod.shows=[mark_source_span(ShowOp(target), source_span_of(target)) for target in show_exprs]
    mod.functions.extend(functions)
    mod.properties.extend(properties)
    mod.entities.extend(entity_decls)
    mod.records.extend(record_decls)
    mod.bindings.extend(bindings)
    mod.states.extend(states)
    mod.state_sets.extend(state_sets)
    mod.ordered_effects.extend(ordered_effects)
    mod.top_level_statements.extend(top_level_statements)
    if imports:
        if base_dir is None:
            raise ParseError("imports require parse_file() or base_dir")
        from pathlib import Path
        for imp in imports:
            # Standard-library modules are compiler-provided namespaces and do
            # not correspond to source files on disk.
            if imp.path.startswith("std."):
                continue
            raw_import = imp.path
            from .project import resolve_import
            path = resolve_import(base_dir, raw_import)
            if path is None:
                raise ParseError(f"import not found: '{imp.path}'")
            if path in _import_stack:
                chain = " -> ".join(str(x) for x in _import_stack + [path])
                raise ParseError(f"cyclic import: {chain}")
            imported = parse(path.read_text(encoding="utf-8"), path.parent, _import_stack + [path])
            if imported.ast.module and mod.module and imported.ast.module.name == mod.module.name:
                raise ParseError(f"module imports itself: '{mod.module.name}'")
            im = imported.ast
            namespace = imp.alias or (im.module.name if im.module else path.stem)
            if namespace in mod.module_exports:
                raise ParseError(f"duplicate imported namespace '{namespace}'")
            module_public = set(im.exports) if im.exports else None
            requested = set(imp.names) if imp.names else None
            available = {fn.name for fn in im.functions} | {d.name for d in im.entities} | {d.name for d in im.records}
            if module_public is not None:
                unknown_public = sorted(module_public - available)
                if unknown_public:
                    raise ParseError(f"module '{namespace}' exports unknown declaration(s): {', '.join(unknown_public)}")
            if requested is not None:
                unknown = sorted(requested - available)
                if unknown:
                    raise ParseError(f"module '{namespace}' does not export: {', '.join(unknown)}")
                if module_public is not None:
                    denied = sorted(requested - module_public)
                    if denied:
                        raise ParseError(f"module '{namespace}' does not publicly export: {', '.join(denied)}")
            allowed = requested if requested is not None else module_public
            exports = {}
            for fn in im.functions:
                if allowed is None or fn.name in allowed:
                    exports[fn.name] = fn
            for decl in im.entities:
                if allowed is None or decl.name in allowed:
                    exports[decl.name] = decl
            for decl in im.records:
                if allowed is None or decl.name in allowed:
                    exports[decl.name] = decl
            mod.module_exports[namespace] = exports
            mod.gravity = mod.gravity or im.gravity
            # A namespace import (`as`) is namespace-only. A selective import
            # merges only the requested public declarations. The old bare
            # source import keeps its legacy merge-all behavior.
            legacy_merge = not imp.alias and not imp.names
            selective_merge = bool(imp.names) and not imp.alias
            merge_names = set(exports) if selective_merge else None
            def keep(name):
                return legacy_merge or (selective_merge and name in merge_names)
            if legacy_merge:
                mod.bodies.extend(im.bodies); mod.datasets.extend(im.datasets); mod.circles.extend(im.circles)
                mod.filters.extend(im.filters); mod.sorts.extend(im.sorts); mod.maps.extend(im.maps)
                mod.aggregates.extend(im.aggregates); mod.reduces.extend(im.reduces); mod.sequences.extend(im.sequences)
                mod.simulations.extend(im.simulations); mod.goals.extend(im.goals); mod.graphs.extend(im.graphs); mod.path_goals.extend(im.path_goals); mod.satisfy_goals.extend(im.satisfy_goals); mod.shows.extend(im.shows)
                mod.bindings.extend(im.bindings); mod.states.extend(im.states); mod.state_sets.extend(im.state_sets); mod.ordered_effects.extend(im.ordered_effects)
                mod.properties.extend(im.properties)
            else:
                exported_types = set(exports)
                mod.properties.extend(prop for prop in im.properties if prop.entity_type in exported_types)
            mod.functions.extend(fn for fn in im.functions if keep(fn.name))
            mod.entities.extend(d for d in im.entities if keep(d.name))
            mod.records.extend(d for d in im.records if keep(d.name))
            for nested_ns, nested_exports in im.module_exports.items():
                if nested_ns not in mod.module_exports:
                    mod.module_exports[nested_ns] = dict(nested_exports)
# Re-export selected public declarations from another source module.
    # Re-exports add to this module's public API but do not merge the source
    # module's private implementation into the caller.
    for re_path, re_names in reexports:
        if re_path.startswith("std."):
            raise ParseError("re-exporting standard-library namespaces is not supported")
        raw_import = re_path
        from .project import resolve_import
        rpath = resolve_import(base_dir, raw_import)
        if rpath is None:
            raise ParseError(f"re-export source not found: '{re_path}'")
        if rpath in _import_stack:
            chain = " -> ".join(str(x) for x in _import_stack + [rpath])
            raise ParseError(f"cyclic import: {chain}")
        rim = parse(rpath.read_text(encoding="utf-8"), rpath.parent, _import_stack + [rpath]).ast
        available = {fn.name: fn for fn in rim.functions} | {d.name: d for d in rim.entities} | {d.name: d for d in rim.records}
        public = set(rim.exports) if rim.exports else set(available)
        unknown = sorted(set(re_names) - public)
        if unknown:
            raise ParseError(f"module '{r_path if False else re_path}' does not publicly export: {', '.join(unknown)}")
        for name in re_names:
            obj = available.get(name)
            if obj is None:
                raise ParseError(f"module '{re_path}' exports unknown declaration '{name}'")
            if any(existing.name == name for existing in mod.functions) or any(existing.name == name for existing in mod.entities) or any(existing.name == name for existing in mod.records):
                raise ParseError(f"duplicate re-export '{name}'")
            if isinstance(obj, FunctionDecl):
                mod.functions.append(obj)
            elif isinstance(obj, EntityDecl):
                mod.entities.append(obj)
            elif isinstance(obj, RecordDecl):
                mod.records.append(obj)
            mod.exports = tuple(dict.fromkeys((*mod.exports, name)))
    # Keep import metadata for diagnostics; declarations are already merged.
        # Rebuild the legacy mirrors after imported declarations have been merged.
        bodies = [BodyDecl(x.name, dict(x.fields)) for x in mod.bodies]
        circles = [Circle(x.name, x.fields["radius"]) for x in mod.circles]
        sim = None
        if mod.simulations:
            q = mod.simulations[0]
            sim = (q.target, q.attractor, q.duration, q.step)
        shows = []
        for op in mod.shows:
            if isinstance(op.target, Name): shows.append((op.target.name, "__value__"))
            elif isinstance(op.target, Property) and isinstance(op.target.base, Name): shows.append((op.target.base.name, op.target.name))
        show_exprs = [op.target for op in mod.shows]
        data_tables = {d.name: d.rows for d in mod.datasets}
        people = []
        for rows in data_tables.values():
            people.extend([DataRow(r.get("name", ""), r.get("age", 0)) for r in rows if "age" in r])
    program = Program(mod.gravity,bodies,sim,shows,show_exprs,people,data_query,circles,mod,data_tables,{},base_dir)
    program._module_exports = mod.module_exports
    return program

def parse_file(path):
    from pathlib import Path
    path = Path(path).resolve()
    return parse(path.read_text(encoding="utf-8"), path.parent, [path])

def _implicit_generic_names(type_refs, known_names):
    """Infer conventional single-letter type parameters from a function signature.

    Explicit ``<T>`` remains available.  When omitted, a previously undeclared
    single uppercase identifier such as ``T`` or ``U`` in the parameter/return
    type references is treated as a generic parameter.  Restricting inference
    to this conventional form keeps ordinary named types unambiguous.
    """
    found = []

    def visit(ref):
        if ref is None:
            return
        if not ref.args:
            name = ref.name
            if (len(name) == 1 and name.isupper() and name not in known_names
                    and name not in found):
                found.append(name)
            return
        for arg in ref.args:
            visit(arg)

    for ref in type_refs:
        visit(ref)
    return tuple(found)


def _resolve_decl_type(ref, record_names, entity_names, generic_names=()):
    """Resolve TypeRef recursively against declared user types."""
    from .types import type_from_ref, contains_type_var
    name = ref.name
    if name in generic_names and not ref.args:
        return type_var('$' + name)
    if name == 'List':
        return list_type(_resolve_decl_type(ref.args[0], record_names, entity_names, generic_names) if ref.args else ANY)
    if name == 'Record':
        if not ref.args:
            return RECORD
        return Type('Record', args=(_resolve_decl_type(ref.args[0], record_names, entity_names, generic_names),))
    if name == 'Entity':
        if not ref.args:
            return Type('Entity')
        return Type('Entity', args=(_resolve_decl_type(ref.args[0], record_names, entity_names, generic_names),))
    if name in record_names:
        return record_type(name, tuple(_resolve_decl_type(a, record_names, entity_names, generic_names) for a in ref.args)) if ref.args else record_type(name)
    if name in entity_names:
        return entity_type(name)
    if name == 'Function':
        raw_args = tuple(_resolve_decl_type(a, record_names, entity_names, generic_names) for a in ref.args)
        if not raw_args:
            return Type('Function')
        effect_names = {'pure', 'state-read', 'state-write', 'io', 'external'}
        raw_refs = list(ref.args)
        effects = []
        while raw_refs and (raw_refs[-1].name in effect_names or raw_refs[-1].name in generic_names) and not raw_refs[-1].args:
            marker = raw_refs.pop().name
            effects.insert(0, '$' + marker if marker in generic_names else marker)
        value_types = tuple(_resolve_decl_type(a, record_names, entity_names, generic_names) for a in raw_refs)
        return function_type(value_types[:-1], value_types[-1], tuple(effects) if effects else None)
    return type_from_ref(ref)


def validate(p:Program):
    # Generic expression/type layer. Every AST expression is checked through
    # the same type environment; domain-specific validators remain below for
    # current runtime constraints.
    registry = domain_registry()
    fields = {"Row": {}, "Record": {}}
    fields.update({name: dict(spec) for name, spec in registry.entities.items()})
    for table in (p.data_tables or {}).values():
        for row in table:
            for k, v in row.items():
                if k == "name": continue
                old = fields["Row"].get(k)
                inferred = BOOLEAN if isinstance(v, bool) else NUMBER if isinstance(v, (int,float)) else TEXT
                if old is not None and old != inferred:
                    fields["Row"][k] = Type("Any")
                else:
                    fields["Row"][k] = inferred
    from .types import type_from_ref, contains_type_var
    record_names = {decl.name for decl in p.ast.records}
    record_params = {decl.name: tuple(decl.type_params) for decl in p.ast.records}
    entity_names = {decl.name for decl in p.ast.entities}
    entity_fields = {}
    for decl in p.ast.entities:
        if decl.name in entity_fields or decl.name == "Row":
            raise TypeError(f"duplicate entity type '{decl.name}'")
        entity_fields[decl.name] = {name: _resolve_decl_type(ref, record_names, entity_names) for name, ref in decl.fields}
    if record_names & set(entity_fields):
        raise TypeError(f"type name declared as both entity and record: {sorted(record_names & set(entity_fields))[0]}")
    record_fields = {decl.name: {name: _resolve_decl_type(ref, record_names, entity_names, decl.type_params) for name, ref in decl.fields} for decl in p.ast.records}
    from .types import record_schema
    p.ast._record_schemas = {name: record_schema(name, fields.items()) for name, fields in record_fields.items()}
    fields.update(entity_fields)
    fields.update(record_fields)
    env = TypeEnv(
        names={"row": Type("Row")} | {b.name: entity_type("Body") for b in p.bodies} | {c.name: entity_type("Circle") for c in (p.circles or [])},
        fields=fields,
        properties={name: dict(props) for name, props in registry.properties.items()},
        functions={name: (fn.parameters, fn.result) for name, fn in registry.functions.items()},
        record_params=record_params,
    )
    # User-defined entity constructors are ordinary typed calls.
    for decl in p.ast.entities:
        env.functions[decl.name] = (tuple(t for _, t in ((name, _resolve_decl_type(ref, record_names, entity_names)) for name, ref in decl.fields)), entity_type(decl.name))
    for decl in p.ast.records:
        generic_names = tuple(decl.type_params)
        params = tuple(_resolve_decl_type(ref, record_names, entity_names, generic_names) for _, ref in decl.fields)
        result_args = tuple(type_var('$' + name) for name in generic_names)
        env.functions[decl.name] = (params, record_type(decl.name, result_args))
    # User-defined functions and computed properties extend the same semantic environment.
    # Register explicit signatures first so generic functions can call other generic functions.
    from .function_effects import analyze_function_effects
    function_effect_contracts = {s.function: s.effects for s in analyze_function_effects(p.ast)}
    known_type_names = set(record_names) | set(entity_names) | {
        "Number", "Boolean", "Text", "Record", "List", "Entity",
        "kg", "m", "s", "mps", "m2", "mps2", "N", "m3_per_kg_s2",
    }
    inferred_generic_names = {}
    for fn in p.ast.functions:
        if fn.name in env.functions:
            raise TypeError(f"duplicate function '{fn.name}'")
        explicit = tuple(fn.type_params)
        parameter_refs = [t for _, t in fn.parameters if t is not None]
        signature_refs = parameter_refs + ([fn.return_type] if fn.return_type else [])
        implicit = _implicit_generic_names(signature_refs, known_type_names | set(explicit)) if not explicit else ()
        if implicit:
            parameter_generic_names = _implicit_generic_names(parameter_refs, known_type_names | set(explicit))
            unbound = [name for name in implicit if name not in parameter_generic_names]
            if unbound:
                raise TypeError(f"function '{fn.name}' has implicit generic type parameter(s) that cannot be inferred from arguments: {', '.join(unbound)}")
        generic_names = explicit + implicit
        inferred_generic_names[fn.name] = generic_names
        params = tuple(_resolve_decl_type(t, record_names, entity_names, generic_names) if t is not None else ANY for _, t in fn.parameters)
        ret = _resolve_decl_type(fn.return_type, record_names, entity_names, generic_names) if fn.return_type else ANY
        # Every declared generic must be recoverable from call arguments. A
        # return-only generic (for example ``f<T>() -> T``) has no deterministic
        # instantiation at a call site and would otherwise degrade to Any.
        # Reject it during semantic analysis, before native/MLIR lowering.
        generic_type_vars = {'$' + name for name in generic_names}
        unbound_generics = [
            name for name, var in zip(generic_names, ('$' + n for n in generic_names))
            if not any(contains_type_var(param, {var}) for param in params)
        ]
        if unbound_generics:
            raise TypeError(
                f"function '{fn.name}' has generic type parameter(s) that cannot be inferred from arguments: {', '.join(unbound_generics)}"
            )
        env.functions[fn.name] = (params, ret)
        # First-class function values carry the inferred effect contract.
        env.names[fn.name] = function_type(params, ret, function_effect_contracts.get(fn.name, ()))
    # Imported user modules expose explicit namespace aliases while retaining
    # legacy unqualified access to imported declarations.
    for namespace, exports in p.ast.module_exports.items():
        for export_name, export in exports.items():
            qualified = f"{namespace}.{export_name}"
            if isinstance(export, FunctionDecl):
                if qualified in env.functions:
                    raise TypeError(f"duplicate imported function '{qualified}'")
                if export.name in env.functions:
                    params, ret = env.functions[export.name]
                else:
                    generic_names = inferred_generic_names.get(export.name, tuple(export.type_params))
                    params = tuple(_resolve_decl_type(t, record_names, entity_names, generic_names) if t is not None else ANY for _, t in export.parameters)
                    ret = _resolve_decl_type(export.return_type, record_names, entity_names, generic_names) if export.return_type else ANY
                env.functions[qualified] = (params, ret)
                env.names[qualified] = function_type(params, ret, function_effect_contracts.get(export.name, ()))
            elif isinstance(export, (EntityDecl, RecordDecl)):
                if qualified in env.functions:
                    raise TypeError(f"duplicate imported constructor '{qualified}'")
                if isinstance(export, EntityDecl):
                    params = tuple(_resolve_decl_type(t, record_names, entity_names) for _, t in export.fields)
                    ret = entity_type(export.name)
                else:
                    params = tuple(_resolve_decl_type(t, record_names, entity_names, export.type_params) for _, t in export.fields)
                    ret = record_type(export.name, tuple(type_var('$' + n) for n in export.type_params))
                env.functions[qualified] = (params, ret)
                env.names[qualified] = function_type(params, ret, ())

    # Infer omitted parameter types from concrete call sites and propagate
    # those types through chains of user-defined function calls.  This is a
    # small deterministic fixed point: a parameter is resolved only from a
    # concrete type already known elsewhere in the call graph.  Generic
    # signatures are checked with the same generic matcher used by ordinary
    # expression inference.
    omitted = {fn.name: [name for name, ref in fn.parameters if ref is None] for fn in p.ast.functions}
    fn_by_name = {fn.name: fn for fn in p.ast.functions}
    candidates = {name: {} for name in omitted}

    def param_index(fn_name, param_name):
        for index, (name, _) in enumerate(fn_by_name[fn_name].parameters):
            if name == param_name:
                return index
        return None

    def add_candidate(fn_name, param_name, typ):
        if typ is None or typ.name == 'Any' or is_type_var(typ):
            return False
        bucket = candidates[fn_name].setdefault(param_name, [])
        if not any(same_or_any(typ, old) and same_or_any(old, typ) for old in bucket):
            bucket.append(typ)
            return True
        return False

    def validate_call_edge(callee_name, args, owner_name):
        """Propagate resolved owner parameter types into omitted callee params."""
        sig = env.functions.get(callee_name)
        if sig is None or callee_name not in omitted:
            return False
        params, _ = sig
        changed = False
        for index, arg in enumerate(args):
            if index >= len(params) or not isinstance(arg, Name):
                continue
            owner_index = param_index(owner_name, arg.name)
            if owner_index is None:
                continue
            owner_type = env.functions[owner_name][0][owner_index]
            if owner_type.name == 'Any' or is_type_var(owner_type):
                continue
            callee_fn = fn_by_name[callee_name]
            callee_param_name = callee_fn.parameters[index][0]
            if callee_param_name not in omitted[callee_name]:
                # The callee is explicitly typed; the ordinary body check will
                # report an incompatibility if the resolved type is wrong.
                continue
            changed |= add_candidate(callee_name, callee_param_name, owner_type)
        return changed

    def collect_calls(expr, owner_name=None):
        changed = False
        if isinstance(expr, Call):
            changed |= validate_call_edge(expr.name, expr.args, owner_name) if owner_name else False
            for arg in expr.args:
                changed |= collect_calls(arg, owner_name)
            return changed
        if isinstance(expr, (Binary, Compare, Logical)):
            changed |= collect_calls(expr.left, owner_name)
            changed |= collect_calls(expr.right, owner_name)
        elif isinstance(expr, (Field, Property)):
            changed |= collect_calls(expr.base, owner_name)
        return changed

    # Seed the graph from concrete top-level calls.  A generic signature is
    # instantiated against the concrete argument just as a normal call would
    # be, so this also supports chains involving generic functions.
    def collect_top(expr):
        changed = False
        if isinstance(expr, Call):
            sig = env.functions.get(expr.name)
            if sig is not None and expr.name in omitted:
                params, _ = sig
                for index, arg in enumerate(expr.args):
                    if index >= len(params):
                        continue
                    if isinstance(arg, Name) and arg.name not in env.names:
                        # Top-level bindings are type-checked later in source
                        # order, but they may already provide concrete call-site
                        # evidence for inferring an unannotated function parameter.
                        # Resolve that evidence from the binding initializer
                        # before asking the environment to resolve the name.
                        actual = None
                        for binding in p.ast.bindings:
                            if binding.name == arg.name:
                                actual = infer(binding.expr, env)
                                break
                        if actual is None:
                            actual = infer(arg, env)
                    else:
                        actual = infer(arg, env)
                    if actual.name == 'Any' and isinstance(arg, Name):
                        for binding in p.ast.bindings:
                            if binding.name == arg.name:
                                actual = infer(binding.expr, env)
                                break
                    if actual.name == 'Any' or is_type_var(actual):
                        continue
                    pname = fn_by_name[expr.name].parameters[index][0]
                    if pname in omitted[expr.name]:
                        changed |= add_candidate(expr.name, pname, actual)
            for arg in expr.args:
                changed |= collect_top(arg)
        elif isinstance(expr, (Binary, Compare, Logical)):
            changed |= collect_top(expr.left); changed |= collect_top(expr.right)
        elif isinstance(expr, (Field, Property)):
            changed |= collect_top(expr.base)
        return changed

    for binding in p.ast.bindings:
        collect_top(binding.expr)

    # Repeatedly propagate resolved parameter types through the call graph.
    # The graph is finite and candidates only grow, so this reaches a stable
    # deterministic point without guessing types.
    changed = True
    while changed:
        changed = False
        for fn in p.ast.functions:
            for stmt in fn.body:
                if isinstance(stmt, (ReturnOp, LetOp)):
                    changed |= collect_calls(stmt.expr, fn.name)
                elif isinstance(stmt, IfOp):
                    changed |= collect_calls(stmt.condition, fn.name)
                    for child in stmt.then_body + stmt.else_body:
                        if isinstance(child, (ReturnOp, LetOp)):
                            changed |= collect_calls(child.expr, fn.name)
        for fn in p.ast.functions:
            params = list(env.functions[fn.name][0])
            for index, (name, ref) in enumerate(fn.parameters):
                if ref is not None:
                    continue
                values = candidates[fn.name].get(name, [])
                if not values:
                    continue
                first = values[0]
                if not all(same_or_any(first, value) and same_or_any(value, first) for value in values[1:]):
                    raise TypeError(f"cannot infer parameter type for '{fn.name}({name})': conflicting call-site types {first} and {values[1]}")
                if params[index] != first:
                    params[index] = first
                    changed = True
            current = env.functions[fn.name]
            env.functions[fn.name] = (tuple(params), current[1])
            env.names[fn.name] = function_type(tuple(params), current[1], function_effect_contracts.get(fn.name, ()))

    # Bidirectional inference: when a function has an explicit return type,
    # propagate that expected type backwards through calls and generic
    # collection primitives.  This handles cases where a parameter is only
    # visible inside a nested expression and there is no direct top-level call
    # supplying a concrete argument.  We only add concrete candidates; no
    # type is guessed from an unconstrained expression.
    def constrain_expr(expr, expected, owner_name, local_exprs=None, visiting=None):
        if expected is None or expected.name == 'Any' or is_type_var(expected):
            return False
        local_exprs = local_exprs or {}
        visiting = set() if visiting is None else visiting
        changed = False
        if isinstance(expr, Name):
            if owner_name in omitted and expr.name in omitted[owner_name]:
                changed |= add_candidate(owner_name, expr.name, expected)
            # Propagate an expected type through a local binding. This makes
            # inference bidirectional across `let` boundaries instead of
            # stopping at the local variable name. A small cycle guard keeps
            # malformed/self-referential constraints deterministic.
            if expr.name in local_exprs and expr.name not in visiting:
                visiting.add(expr.name)
                changed |= constrain_expr(local_exprs[expr.name], expected, owner_name, local_exprs, visiting)
                visiting.remove(expr.name)
            return changed
        if isinstance(expr, Call):
            sig = env.functions.get(expr.name)
            if sig is None:
                return False
            params, result = sig
            bindings = {}
            if not generic_match(result, expected, bindings):
                return False
            for index, arg in enumerate(expr.args):
                if index >= len(params):
                    break
                arg_expected = substitute_type(params[index], bindings)
                if arg_expected.name == 'Any' or is_type_var(arg_expected):
                    continue
                changed |= constrain_expr(arg, arg_expected, owner_name, local_exprs, visiting)
            return changed
        if isinstance(expr, (Binary, Compare, Logical)):
            # Arithmetic/logical expressions have deliberately conservative
            # reverse rules.  Number is unambiguous for numeric +,-,*,/,^;
            # Boolean is unambiguous for logical operators.
            if isinstance(expr, Logical):
                if expected == BOOLEAN:
                    changed |= constrain_expr(expr.left, BOOLEAN, owner_name, local_exprs, visiting)
                    if expr.right is not None:
                        changed |= constrain_expr(expr.right, BOOLEAN, owner_name, local_exprs, visiting)
                return changed
            if isinstance(expr, Binary) and expected == NUMBER and expr.op in ('+','-','*','/','^','%'):
                changed |= constrain_expr(expr.left, NUMBER, owner_name, local_exprs, visiting)
                changed |= constrain_expr(expr.right, NUMBER, owner_name, local_exprs, visiting)
                return changed
            if isinstance(expr, Compare) and expected == BOOLEAN:
                # Comparisons do not reveal a unique operand type, so do not
                # manufacture a type here.
                return False
            return False
        if isinstance(expr, (Field, Property)):
            return False
        return False

    for fn in p.ast.functions:
        declared_return = _resolve_decl_type(fn.return_type, record_names, entity_names, inferred_generic_names[fn.name]) if fn.return_type else None
        if declared_return is not None:
            local_exprs = {}
            def constrain_block(body):
                for stmt in body:
                    if isinstance(stmt, LetOp):
                        local_exprs[stmt.name] = stmt.expr
                    elif isinstance(stmt, ReturnOp):
                        constrain_expr(stmt.expr, declared_return, fn.name, local_exprs)
                    elif isinstance(stmt, IfOp):
                        constrain_block(stmt.then_body)
                        constrain_block(stmt.else_body)
            constrain_block(fn.body)

    # Apply any new candidates and repeat once through the ordinary call graph
    # propagation.  Candidate sets only grow, so this remains deterministic.
    changed = True
    while changed:
        changed = False
        for fn in p.ast.functions:
            params = list(env.functions[fn.name][0])
            for index, (name, ref) in enumerate(fn.parameters):
                if ref is not None:
                    continue
                values = candidates[fn.name].get(name, [])
                if not values:
                    continue
                first = values[0]
                if not all(same_or_any(first, value) and same_or_any(value, first) for value in values[1:]):
                    raise TypeError(f"cannot infer parameter type for '{fn.name}({name})': conflicting call-site types {first} and {values[1]}")
                if params[index] != first:
                    params[index] = first
                    changed = True
            current = env.functions[fn.name]
            env.functions[fn.name] = (tuple(params), current[1])
            env.names[fn.name] = function_type(tuple(params), current[1], function_effect_contracts.get(fn.name, ()))

    for fn in p.ast.functions:
        for index, (name, ref) in enumerate(fn.parameters):
            if ref is None and env.functions[fn.name][0][index].name == 'Any':
                raise TypeError(f"cannot infer parameter type for '{fn.name}({name})'; add an explicit type annotation")

    # Register mutable state names before validating function bodies so
    # functions and returned closures can capture global state. Their
    # initializer types are inferred in declaration order, matching runtime
    # initialization semantics.
    for state in p.ast.states:
        if state.name in env.names:
            raise TypeError(f"duplicate top-level state '{state.name}'")
        env.names[state.name] = infer(state.expr, env)

    for fn in p.ast.functions:
        generic_names = inferred_generic_names[fn.name]
        local_names = dict(env.names)
        local_names.update({n:( _resolve_decl_type(t, record_names, entity_names, generic_names) if t is not None else env.functions[fn.name][0][i]) for i,(n,t) in enumerate(fn.parameters)})
        local = TypeEnv(
            names=local_names, fields=env.fields, properties=env.properties, functions=env.functions,
            record_params=env.record_params, function_effect_contracts=function_effect_contracts,
            scope_prefix=fn.name
        )
        inferred = infer_block(fn.body, local)
        declared = _resolve_decl_type(fn.return_type, record_names, entity_names, generic_names) if fn.return_type else inferred
        # If a function returns a first-class Function without an explicit
        # effect contract, preserve the inferred contract of that value.
        if fn.return_type and is_function(declared) and declared.effects is None and is_function(inferred):
            declared = function_type(function_params(declared), function_result(declared), function_effects(inferred))
        if not unify_types(declared, inferred, {}):
            exc = TypeError(f"function '{fn.name}' returns {inferred}, declared {declared}")
            exc.diagnostic_code = "E2000"
            exc.diagnostic_data = {
                "expected_type": str(declared),
                "actual_type": str(inferred),
                "construct": "function_return",
            }
            raise exc
        env.functions[fn.name] = (env.functions[fn.name][0], declared)
        env.names[fn.name] = function_type(env.functions[fn.name][0], declared, function_effect_contracts.get(fn.name, ()))
    for prop in p.ast.properties:
        if prop.entity_type not in env.properties:
            env.properties[prop.entity_type] = {}
        # A source module can override a standard-domain property explicitly.
        local = TypeEnv(names={"self": entity_type(prop.entity_type)}, fields=env.fields, properties=env.properties, functions=env.functions, record_params=env.record_params)
        inferred = infer_block(prop.body, local)
        declared = type_from_ref(prop.return_type) if prop.return_type else inferred
        if not unify_types(declared, inferred, {}):
            exc = TypeError(f"property '{prop.entity_type}.{prop.name}' returns {inferred}, declared {declared}")
            exc.diagnostic_code = "E2000"
            exc.diagnostic_data = {
                "expected_type": str(declared),
                "actual_type": str(inferred),
                "construct": "property_return",
            }
            raise exc
        env.properties[prop.entity_type][prop.name] = declared
    # State names were registered before function-body checking so closures
    # can capture them. Validate updates after all function return types have
    # been resolved.
    for state_set in p.ast.state_sets:
        if state_set.name not in env.names:
            raise TypeError(f"unknown state '{state_set.name}'")
        value_type = infer(state_set.expr, env)
        if not unify_types(env.names[state_set.name], value_type, {}):
            raise TypeError(f"state '{state_set.name}' update returns {value_type}, expected {env.names[state_set.name]}")
    # Reserve names produced by declarative scalar dataflow operations before
    # checking ordinary bindings. A binding may legitimately depend on an
    # aggregate result declared in the same program (for example, `let flag =
    # if peak >= 30 then ...`). The concrete result types are inferred by the
    # collection dependency pass below; these placeholders only make those
    # names visible during the initial binding pass.
    dataflow_result_names = {
        op.result
        for op in (
            *p.ast.filters,
            *p.ast.sorts,
            *p.ast.maps,
            *p.ast.aggregates,
            *p.ast.reduces,
            *p.ast.conditional_pipelines,
        )
    }
    for result_name in dataflow_result_names:
        if result_name not in env.names:
            env.names[result_name] = ANY

    # Top-level bindings are ordinary typed values.
    for binding in p.ast.bindings:
        if binding.name in env.names:
            raise TypeError(f"duplicate top-level binding '{binding.name}'")
        env.names[binding.name] = infer(binding.expr, env)

    # Collections are typed values. Their element type is inferred through
    # the dependency graph, so map/filter/sort/aggregate can be chained
    # without falling back to List<Any>.
    row_type = Type("Row")
    collection_types = {name: list_type(row_type) for name in (p.data_tables or {})}
    for binding in p.ast.bindings:
        binding_type = env.names.get(binding.name, ANY)
        if is_list(binding_type):
            collection_types[binding.name] = binding_type
    # Sequences are typed collections whose element type is inferred from the initial state.
    for seq in p.ast.sequences:
        initial_type = infer(seq.initial, env)
        local_seq = TypeEnv(dict(env.names), env.fields, env.properties, env.functions, env.record_params)
        local_seq.names['value'] = initial_type
        step_type = infer(seq.expr, local_seq)
        if not unify_types(initial_type, step_type, {}):
            raise TypeError(f"sequence '{seq.result}' step returns {step_type}, expected {initial_type}")
        if seq.until is not None:
            until_type = infer(seq.until, local_seq)
            if not unify_types(BOOLEAN, until_type, {}):
                raise TypeError(f"sequence '{seq.result}' until condition must be Boolean, got {until_type}")
        if seq.target is not None:
            target_type = infer(seq.target, local_seq)
            if not unify_types(initial_type, target_type, {}):
                raise TypeError(f"sequence '{seq.result}' target returns {target_type}, expected {initial_type}")
            for candidate in seq.candidates:
                candidate_type = infer(candidate, local_seq)
                if not unify_types(initial_type, candidate_type, {}):
                    raise TypeError(f"sequence '{seq.result}' transition candidate returns {candidate_type}, expected {initial_type}")
            constraints = seq.constraints or ((seq.constraint,) if seq.constraint is not None else ())
            if constraints:
                constraint_env = TypeEnv(dict(local_seq.names), env.fields, env.properties, env.functions)
                constraint_env.names['candidate'] = initial_type
                for constraint in constraints:
                    constraint_type = infer(constraint, constraint_env)
                    if not unify_types(BOOLEAN, constraint_type, {}):
                        raise TypeError(f"sequence '{seq.result}' satisfy constraint must be Boolean, got {constraint_type}")
        env.names[seq.result] = list_type(initial_type)
        collection_types[seq.result] = list_type(initial_type)
    env.names.update(collection_types)
    p._collection_types = dict(collection_types)

    graph_names = {g.name for g in p.ast.graphs}
    for pg in p.ast.path_goals:
        if pg.source not in graph_names:
            raise TypeError(f"unknown graph '{pg.source}'")
        if pg.objective != 'cost':
            raise TypeError(f"unsupported path objective '{pg.objective}'")
        if not any(pg.start in (a,b) and pg.end in (a,b) for a,b,_,_ in next(g.edges for g in p.ast.graphs if g.name == pg.source)):
            # A disconnected endpoint is legal syntactically; runtime reports no path.
            pass

    for pg in p.ast.path_goals:
        env.names[pg.result] = Type('Path')

    # Selection-goal results are available to later declarative goals. Reserve
    # their record type before validating satisfy constraints so expressions
    # such as `x + y == best.age` can resolve the preceding `choose` binding.
    for goal in p.ast.goals:
        env.names.setdefault(goal.result, Type('Row'))

    for sg in p.ast.satisfy_goals:
        local_env = TypeEnv(dict(env.names), env.fields, env.properties, env.functions, env.record_params)
        for name, _, _ in sg.variables:
            local_env.names[name] = NUMBER
        for constraint in sg.constraints:
            constraint_type = infer(constraint, local_env)
            if constraint_type != BOOLEAN:
                raise TypeError(f"satisfy constraint must be Boolean, got {constraint_type}")
        env.names[sg.result] = Type('Solution')

    goal_results = {g.result for g in p.ast.goals}
    def apply_pipeline_function(value_type, input_types, label, expected_result=None):
        """Validate a higher-order pipeline function through one type contract.

        Parameter types, generic bindings, function results, and (when present)
        effect contracts all use the same recursive unification relation.
        ``expected_result`` lets operations such as ``where`` and ``aggregate``
        constrain the returned value without introducing a second matcher.
        """
        if not is_function(value_type):
            if expected_result is not None:
                bindings = {}
                if not unify_types(expected_result, value_type, bindings):
                    raise TypeError(f"{label} result expects {expected_result}, got {value_type}")
                return substitute_type(value_type, bindings), bindings
            return value_type, {}
        params = function_params(value_type)
        if len(params) != len(input_types):
            raise TypeError(f"{label} function expects {len(params)} argument(s), got {len(input_types)}")
        bindings = {}
        for expected, actual in zip(params, input_types):
            if not unify_types(expected, actual, bindings):
                if label == "where" and expected_result is not None:
                    raise TypeError(
                        f"where function parameter expects {substitute_type(expected, bindings)}, got {actual}; where function must return Boolean"
                    )
                raise TypeError(
                    f"{label} function parameter expects {substitute_type(expected, bindings)}, got {actual}"
                )
        result = substitute_type(function_result(value_type), bindings)
        if expected_result is not None:
            if not unify_types(expected_result, result, bindings):
                raise TypeError(f"{label} function result expects {expected_result}, got {result}")
            result = substitute_type(result, bindings)
        return result, bindings

    operations = ([('filter', x) for x in p.ast.filters] +
                  [('sort', x) for x in p.ast.sorts] +
                  [('conditional_pipeline', x) for x in p.ast.conditional_pipelines] +
                  [('map', x) for x in p.ast.maps] +
                  [('aggregate', x) for x in p.ast.aggregates] +
                  [('reduce', x) for x in p.ast.reduces] +
                  [('goal', x) for x in p.ast.goals])
    # Type-check rebinding pipelines in source order. The AST stores operation
    # kinds in separate lists, so category order alone can incorrectly type a
    # `where item ...` as if it still consumed the original Record collection.
    from .ast import source_span_of
    operations = sorted(operations, key=lambda pair: (
        source_span_of(pair[1]).start.line if source_span_of(pair[1]) else 10**9,
        source_span_of(pair[1]).start.column if source_span_of(pair[1]) else 10**9,
    ))
    remaining = list(operations)
    while remaining:
        progress = False
        next_remaining = []
        for kind, op in remaining:
            # Names produced by collection operations are reserved in env.names
            # as Any before dependency resolution.  That placeholder must not be
            # mistaken for a resolved source: e.g. a `where` after `sort` can
            # otherwise consume the sort result before the sort has inferred its
            # concrete List<Record<...>> type.  collection_types contains only
            # values whose collection/dataflow type has actually been resolved.
            source_is_resolved = op.source in collection_types
            source_type = collection_types.get(op.source, env.names.get(op.source, ANY))
            singleton_goal_source = kind == 'goal' and op.source in goal_results and source_type.name == 'Row'
            if not source_is_resolved and not singleton_goal_source:
                next_remaining.append((kind, op))
                continue
            if not is_list(source_type) and not singleton_goal_source:
                raise TypeError(f"collection '{op.source}' has type {source_type}, expected List")
            item_type = Type('Row') if singleton_goal_source else list_item_type(source_type)
            local_env = TypeEnv(dict(env.names), env.fields, env.properties, env.functions, env.record_params)
            local_env.names['row'] = item_type
            local_env.names['item'] = item_type
            if kind == 'filter':
                predicate_type = infer(op.predicate.expr, local_env)
                if is_function(predicate_type):
                    predicate_result, _ = apply_pipeline_function(predicate_type, (item_type,), "where", BOOLEAN)
                elif predicate_type != BOOLEAN:
                    raise TypeError(f"where condition must be Boolean, got {predicate_type}")
                result_type = collection_preserve_type(source_type)
            elif kind == 'conditional_pipeline':
                if infer(op.condition, env) != BOOLEAN:
                    raise TypeError("conditional pipeline condition must be Boolean")

                def branch_type(stages, initial_type):
                    current_type=initial_type
                    for stage_kind, stage_expr in stages:
                        if not is_list(current_type):
                            raise TypeError(f"conditional pipeline stage '{stage_kind}' requires a collection, got {current_type}")
                        item= list_item_type(current_type)
                        stage_env=TypeEnv(dict(env.names), env.fields, env.properties, env.functions, env.record_params)
                        stage_env.names['row']=item
                        stage_env.names['item']=item
                        if stage_kind == 'where':
                            predicate_type = infer(stage_expr.expr, stage_env)
                            if is_function(predicate_type):
                                apply_pipeline_function(predicate_type, (item,), "conditional pipeline where", BOOLEAN)
                            elif not unify_types(BOOLEAN, predicate_type, {}):
                                raise TypeError("conditional pipeline where condition must be Boolean")
                            current_type=collection_preserve_type(current_type)
                        elif stage_kind == 'sort':
                            key_type=infer(stage_expr.expr, stage_env)
                            if key_type.name in ('List','Any'):
                                raise TypeError(f"sort key must be a scalar value, got {key_type}")
                            current_type=collection_preserve_type(current_type)
                        elif stage_kind == 'map':
                            mapped = infer(stage_expr, stage_env)
                            if is_function(mapped):
                                mapped, _ = apply_pipeline_function(mapped, (item,), "conditional pipeline map")
                            current_type=collection_map_type(current_type, mapped)
                        elif stage_kind == 'aggregate':
                            name, expr=stage_expr
                            if name == 'count':
                                current_type=NUMBER
                            else:
                                value_type=infer(expr, stage_env)
                                if is_function(value_type):
                                    value_type, _ = apply_pipeline_function(value_type, (item,), f"aggregate '{name}'")
                                if value_type.name not in ('Number','Quantity'):
                                    raise TypeError(f"aggregate '{name}' requires a numeric expression, got {value_type}")
                                current_type=value_type
                        elif stage_kind == 'reduce':
                            initial_expr, step_expr=stage_expr
                            acc_type=infer(initial_expr, stage_env)
                            reduce_env=TypeEnv(dict(stage_env.names), stage_env.fields, stage_env.properties, stage_env.functions, stage_env.record_params)
                            reduce_env.names['acc']=acc_type
                            if not unify_types(acc_type, infer(step_expr, reduce_env), {}):
                                raise TypeError("conditional pipeline reduce type mismatch")
                            current_type=acc_type
                        else:
                            raise TypeError(f"unknown conditional pipeline operation '{stage_kind}'")
                    return current_type

                then_type=branch_type(op.then_stages, source_type)
                else_type=branch_type(op.else_stages, source_type)
                if not unify_types(then_type, else_type, {}):
                    raise TypeError("conditional pipeline branches must have compatible types")
                result_type=then_type
            elif kind == 'sort':
                key_type = infer(op.spec.expr, local_env)
                if is_function(key_type):
                    key_type, _ = apply_pipeline_function(key_type, (item_type,), "sort")
                if key_type.name == 'List':
                    raise TypeError(f"sort key must be a scalar value, got {key_type}")
                result_type = collection_preserve_type(source_type)
            elif kind == 'map':
                mapped_type = infer(op.expr, local_env)
                if is_function(mapped_type):
                    mapped_type, _ = apply_pipeline_function(mapped_type, (item_type,), "map")
                result_type = collection_map_type(source_type, mapped_type)
            elif kind == 'aggregate':
                if op.operation == 'count':
                    result_type = NUMBER
                else:
                    value_type = infer(op.expr, local_env)
                    if is_function(value_type):
                        value_type, _ = apply_pipeline_function(value_type, (item_type,), f"aggregate '{op.operation}'")
                    if op.operation in {'min', 'max'} and value_type.name == 'Text':
                        result_type = value_type
                    elif op.operation in {'any', 'all'} and value_type.name == 'Boolean':
                        result_type = BOOLEAN
                    elif value_type.name not in ('Number', 'Quantity'):
                        raise TypeError(f"aggregate '{op.operation}' requires a numeric expression, got {value_type}")
                    else:
                        result_type = value_type
            elif kind == 'reduce':
                initial_type = infer(op.initial, local_env)
                local_env.names['acc'] = initial_type
                step_type = infer(op.expr, local_env)
                if not unify_types(initial_type, step_type, {}):
                    raise TypeError(f"reduce step returns {step_type}, expected accumulator type {initial_type}")
                result_type = collection_reduce_type(initial_type)
            else:
                if op.predicate is not None:
                    predicate_type = infer(op.predicate.expr, local_env)
                    if is_function(predicate_type):
                        apply_pipeline_function(predicate_type, (item_type,), "where", BOOLEAN)
                    elif not unify_types(BOOLEAN, predicate_type, {}):
                        raise TypeError(f"choose condition must be Boolean, got {predicate_type}")
                key_type = infer(op.key, local_env)
                if key_type.name in ('List', 'Any', 'Boolean', 'Row', 'Entity'):
                    raise TypeError(f"choose key must be an orderable scalar value, got {key_type}")
                result_type = item_type
            env.names[op.result] = result_type
            collection_types[op.result] = result_type
            p._collection_types = dict(collection_types)
            progress = True
        if not progress:
            missing = sorted({op.source for _, op in next_remaining if op.source not in env.names})
            if missing:
                raise TypeError(f"unknown collection '{missing[0]}'")
            unresolved = ', '.join(op.result for _, op in next_remaining)
            raise TypeError(f"cannot type collection operations: {unresolved}")
        remaining = next_remaining

    # Persist the fully resolved collection type map on the AST module so the
    # canonical ExecutionIR can carry semantic collection types forward.
    p.ast._collection_types = dict(collection_types)
    p.ast._semantic_type_names = {name: str(typ) for name, typ in env.names.items()}

    # Validate top-level control-flow statements with lexical block scopes.
    # This deliberately shares the same expression/type checker as function bodies.
    def _copy_type_env(source_env):
        return TypeEnv(
            names=dict(source_env.names), fields=source_env.fields,
            properties=source_env.properties, functions=source_env.functions,
            record_params=source_env.record_params,
            function_effect_contracts=source_env.function_effect_contracts,
            scope_prefix=source_env.scope_prefix,
        )

    def _validate_top_level_statements(statements, local_env, inherited_locals=None):
        declared_here = set(inherited_locals or ())
        for statement in statements:
            if isinstance(statement, LetOp):
                if statement.name in declared_here:
                    raise TypeError(f"duplicate local variable '{statement.name}'")
                declared_here.add(statement.name)
                local_env.names[statement.name] = infer(statement.expr, local_env)
            elif isinstance(statement, ShowOp):
                infer(statement.target, local_env)
            elif isinstance(statement, LocalCollectionOp):
                from .semantic import infer_block_partial
                infer_block_partial([statement], local_env)
            elif isinstance(statement, IfOp):
                condition_type = infer(statement.condition, local_env)
                if not unify_types(BOOLEAN, condition_type, {}):
                    raise TypeError(f"if condition must be Boolean, got {condition_type}")
                _validate_top_level_statements(statement.then_body, _copy_type_env(local_env), declared_here)
                _validate_top_level_statements(statement.else_body, _copy_type_env(local_env), declared_here)
            else:
                raise TypeError(f"unsupported top-level statement {type(statement).__name__}")

    if p.ast.top_level_statements:
        _validate_top_level_statements(p.ast.top_level_statements, _copy_type_env(env))

    # Final expression checks use the now-complete collection environment.
    for show in p.ast.shows:
        infer(show.target, env)
    for expr in (p.show_exprs or []):
        infer(expr, env)
    # Physical domain.
    if p.bodies or p.simulation or p.gravity:
        if p.bodies and not p.gravity and p.simulation: raise TypeError("simulation requires 'physics gravity'")
        if p.gravity and not p.bodies: raise TypeError("physics gravity requires at least one body")
        names={b.name for b in p.bodies}
        if len(names)!=len(p.bodies): raise TypeError("duplicate body name")
        for b in p.bodies:
            for f in b.fields:
                if f not in {"mass","position","velocity"}: raise TypeError(f"unknown Body field '{f}'")
            if "mass" in b.fields and b.fields["mass"].unit!="kg": raise TypeError(f"{b.name}.mass must have unit kg")
            if "position" in b.fields and b.fields["position"].unit!="m": raise TypeError(f"{b.name}.position must have unit m")
            if "velocity" in b.fields and b.fields["velocity"].unit!="mps": raise TypeError(f"{b.name}.velocity must have unit mps")
        if p.simulation:
            target, attractor, duration, step=p.simulation
            if target not in names or attractor not in names: raise TypeError("simulate refers to unknown body")
            if target==attractor: raise TypeError("a body cannot orbit itself")
            if duration<=0 or step<=0: raise TypeError("simulation duration and step must be positive")
            by={b.name:b for b in p.bodies}
            for n in (target,attractor):
                if "mass" not in by[n].fields: raise TypeError(f"{n} requires mass")
            if "position" not in by[target].fields or "velocity" not in by[target].fields:
                raise TypeError(f"{target} requires position and velocity for gravity simulation")
    # Data-domain names have already been validated by the generic typed
    # collection pass above.
    # Geometry domain.
    for c in p.circles or []:
        if c.radius.unit != "m" or c.radius.value <= 0: raise TypeError(f"{c.name}.radius must be a positive length in m")
    # Validate show targets.
    body_names={b.name for b in p.bodies}
    entity_bindings={b.name: b for b in p.ast.bindings}
    entity_names={b.name for b in p.ast.bindings if env.names.get(b.name, ANY).name == 'Entity'}
    circle_names={c.name for c in (p.circles or [])}
    for n,f in p.shows:
        if n in entity_names:
            binding_type=env.names.get(n, ANY)
            entity_name=binding_type.args[0].name if binding_type.name == 'Entity' and binding_type.args else None
            if entity_name is None:
                raise TypeError(f"'{n}' is not an entity value")
            allowed=set(fields.get(entity_name, {})) | {x.name for x in p.ast.properties if x.entity_type==entity_name}
            if f != '__value__' and f not in allowed: raise TypeError(f"unknown field '{f}' on {entity_name}")
            continue
        if n in {b.name for b in p.ast.bindings}:
            binding_type = env.names.get(n, ANY)
            if f != '__value__' and binding_type.name not in ('Record', 'Entity'):
                raise TypeError(f"'{n}' is not a structured value")
            continue
        if n in body_names:
            allowed={"mass","position","velocity"} | {x.name for x in p.ast.properties if x.entity_type=="Body"}
            if f not in allowed: raise TypeError(f"unknown field '{f}'")
        elif n in circle_names:
            allowed={"area","circumference","radius"} | {x.name for x in p.ast.properties if x.entity_type=="Circle"}
            if f not in allowed: raise TypeError(f"unknown circle property '{f}'")
        elif n in {st.name for st in p.ast.states}:
            if f != "__value__": raise TypeError(f"state '{n}' has no property '{f}'")
        elif n in {f.result for f in p.ast.filters} | {o.result for o in p.ast.sorts} | {c.result for c in p.ast.conditional_pipelines} | {m.result for m in p.ast.maps} | {a.result for a in p.ast.aggregates} | {r.result for r in p.ast.reduces} | {q.result for q in p.ast.sequences} | {g.result for g in p.ast.goals} | {g.result for g in p.ast.path_goals} | {g.result for g in p.ast.satisfy_goals}:
            goal = next((g for g in p.ast.goals if g.result == n), None)
            if goal is not None and f != "__value__":
                result_type = env.names.get(n, ANY)
                if result_type.name == 'Row' and f not in fields.get('Row', {}):
                    raise TypeError(f"unknown property '{f}' on collection '{n}'")
            elif f != "__value__":
                raise TypeError(f"unknown property '{f}' on collection '{n}'")
        else: raise TypeError(f"show refers to unknown value '{n}'")


def type_name_for_value(value):
    if isinstance(value, RecordValue): return value.type_name or "Record"
    if isinstance(value, UserEntity): return value.type_name
    if isinstance(value, Body): return "Body"
    if isinstance(value, Circle): return "Circle"
    if isinstance(value, dict): return "Row"
    return type(value).__name__

def _resolve_io_path(p, raw_path):
    from pathlib import Path
    path = Path(raw_path)
    if not path.is_absolute() and getattr(p, 'base_dir', None) is not None:
        path = Path(p.base_dir) / path
    return path


def _runtime_function_type(value):
    """Return the static function type carried by a runtime callable value."""
    if isinstance(value, FunctionValue) and value.decl is not None:
        params = []
        for _, ref in value.decl.parameters:
            params.append(_resolve_runtime_type_ref(ref))
        result = _resolve_runtime_type_ref(value.decl.return_type)
        return function_type(params, result)
    if isinstance(value, ComposedFunctionValue):
        inner_t = _runtime_function_type(value.inner)
        outer_t = _runtime_function_type(value.outer)
        from .types import function_effects
        outer_effects = function_effects(outer_t)
        inner_effects = function_effects(inner_t)
        if outer_effects is None or inner_effects is None:
            effects = None
        else:
            effects = tuple(sorted(set(outer_effects) | set(inner_effects)))
        return function_type((function_params(inner_t)[0],), function_result(outer_t), effects)
    raise TypeError('value is not a Function')

def _resolve_runtime_type_ref(ref):
    if ref is None:
        return ANY
    try:
        return _resolve_decl_type(ref, set(), set())
    except Exception:
        return ANY

def _eval_expr(expr, p, row=None, local=None):
    """Compatibility wrapper for the reference interpreter.

    Actual expression semantics live in ``plan_expression`` so the plan runtime
    no longer depends on the reference evaluator for ordinary expressions.
    """
    from .reference_expression import eval_expr
    return eval_expr(expr, p, row, local)

def _eval_pipeline_expr(expr, p, row):
    from .reference_expression import eval_pipeline_expr
    return eval_pipeline_expr(expr, p, row)


class _ReturnSignal:
    def __init__(self, value):
        self.value = value

def _execute_local_collection(values, stages, program, scope):
    """Execute local collection stages in the current lexical scope."""
    current = values
    for operation, expression, initial, direction in stages:
        if not isinstance(current, (list, tuple)):
            raise TypeError(f"collection operation '{operation}' requires a List")
        if operation == "where":
            selected = []
            for item in current:
                value = _eval_expr(expression, program, row=item, local={**scope, "item": item, "row": item})
                if not isinstance(value, bool):
                    raise TypeError("where condition must evaluate to Boolean")
                if value: selected.append(item)
            current = selected
        elif operation == "map":
            current = [_eval_expr(expression, program, row=item, local={**scope, "item": item, "row": item}) for item in current]
        elif operation == "sort":
            current = sorted(current, key=lambda item: _eval_expr(expression, program, row=item, local={**scope, "item": item, "row": item}), reverse=(direction == "desc"))
        elif operation == "reduce":
            accumulator = _eval_expr(initial, program, local=scope)
            for item in current:
                accumulator = _eval_expr(expression, program, row=item, local={**scope, "item": item, "row": item, "acc": accumulator})
            current = accumulator
        elif operation == "count":
            current = len(current)
        elif operation in {"sum", "max", "min", "average", "avg", "any", "all"}:
            items = current if expression is None else [_eval_expr(expression, program, row=item, local={**scope, "item": item, "row": item}) for item in current]
            if operation == "sum": current = sum(items)
            elif operation == "max": current = max(items)
            elif operation == "min": current = min(items)
            elif operation in {"average", "avg"}:
                if not items: raise ValueError("average of an empty collection is undefined")
                current = sum(items) / len(items)
            elif operation == "any": current = any(items)
            elif operation == "all": current = all(items)
        else:
            raise TypeError(f"unsupported local collection operation '{operation}'")
    return current

def _eval_block_raw(body, p, row=None, local=None):
    scope = dict(local or {})
    for stmt in body:
        if isinstance(stmt, FunctionDecl):
            if stmt.name in scope:
                raise TypeError(f"duplicate local variable '{stmt.name}'")
            scope[stmt.name] = FunctionValue(stmt, p, closure=scope)
        elif isinstance(stmt, LetOp):
            if stmt.name in scope:
                raise TypeError(f"duplicate local variable '{stmt.name}'")
            scope[stmt.name] = _eval_expr(stmt.expr, p, row, scope)
        elif isinstance(stmt, LocalCollectionOp):
            if stmt.name in scope:
                raise TypeError(f"duplicate local variable '{stmt.name}'")
            source_value = scope.get(stmt.source)
            if source_value is None:
                source_value = _eval_expr(Name(stmt.source), p, row, scope)
            scope[stmt.name] = _execute_local_collection(source_value, stmt.stages, p, scope)
        elif isinstance(stmt, ReturnOp):
            return _ReturnSignal(_eval_expr(stmt.expr, p, row, scope))
        elif isinstance(stmt, IfOp):
            condition = _eval_expr(stmt.condition, p, row, scope)
            if not isinstance(condition, bool):
                raise TypeError("if condition must evaluate to Boolean")
            branch = stmt.then_body if condition else stmt.else_body
            if branch:
                signal = _eval_block_raw(branch, p, row, scope)
                if isinstance(signal, _ReturnSignal):
                    return signal
        else:
            raise TypeError(f"unsupported statement {type(stmt).__name__}")
    return None

def _eval_block(body, p, row=None, local=None):
    signal = _eval_block_raw(body, p, row, local)
    if isinstance(signal, _ReturnSignal):
        return signal.value
    raise TypeError("block completed without return")

def _goal_distance(candidate, target):
    """Deterministic semantic distance for goal-directed transitions.

    Scalars use absolute distance. Structured UserEntity values use the sum
    of per-field distances in declaration order, allowing goal-directed
    transitions to operate on compound state without exposing a search loop.
    """
    if isinstance(candidate, UserEntity) and isinstance(target, UserEntity):
        if candidate.type_name != target.type_name:
            raise TypeError(f"goal target type mismatch: {candidate.type_name} vs {target.type_name}")
        if tuple(candidate.fields) != tuple(target.fields):
            raise TypeError("goal target structured state fields do not match")
        return sum(_goal_distance(candidate.fields[name], target.fields[name]) for name in candidate.fields)
    if isinstance(candidate, dict) and isinstance(target, dict):
        if tuple(candidate) != tuple(target):
            raise TypeError("goal target structured fields do not match")
        return sum(_goal_distance(candidate[name], target[name]) for name in candidate)
    if isinstance(candidate, (int, float)) and isinstance(target, (int, float)):
        return abs(candidate - target)
    if isinstance(candidate, Quantity) and isinstance(target, Quantity):
        if candidate.dim() != target.dim():
            raise TypeError("goal target quantities must have matching dimensions")
        return abs(candidate.value - target.value)
    raise TypeError(f"goal-directed distance is not defined for {type(candidate).__name__} and {type(target).__name__}")

def show_expr_value(p:Program, expr):
    value=_eval_expr(expr,p)
    if isinstance(value,Quantity): return f"{value.value:.15g} {value.unit}"
    if isinstance(value,float): return f"{value:.15g}"
    if isinstance(value, GraphPath):
        return f"path = {' -> '.join(value.nodes)}, cost = {value.cost:g}"
    if isinstance(value,list):
        if all(isinstance(x, str) for x in value): return '[' + ', '.join(repr(x) for x in value) + ']'
        parts=[]
        for row in value:
            if isinstance(row,dict):
                rest=', '.join(f"{k}={v}" for k,v in row.items() if k != 'name')
                parts.append(f"{row.get('name','row')}({rest})")
            else: parts.append(str(row))
        return '[' + ', '.join(parts) + ']'
    return str(value)

def run(p:Program):
    validate(p)
    # Optimization is semantics-preserving and operates on the declarative IR.
    optimize_program(p)
    # Collection operations form a small declarative dataflow graph.  Their
    # execution order is derived from source availability, not from operation
    # category, so map/filter/sort/aggregate can be freely composed.
    p.entities = {}
    p._bindings = {}
    p._states = {}
    for state in p.ast.states:
        if state.name in p._states: raise TypeError(f"duplicate state '{state.name}'")
        p._states[state.name] = _eval_expr(state.expr, p)
    deferred_dataflow_calls = {"group_by", "group_count", "group_sum", "group_average", "group_min", "group_max"}
    deferred_bindings = []
    # A normal binding may depend on the scalar result of a declarative
    # collection operation (for example: `let verdict = if peak >= 30 then ...`).
    # Those results do not exist until the dataflow scheduler has run, so do not
    # evaluate such bindings eagerly with the initial scalar environment.
    dataflow_scalar_results = {op.result for op in (*p.ast.aggregates, *p.ast.reduces)}
    from .semantic_graph import _expr_names as _semantic_expr_names
    for binding in p.ast.bindings:
        if (isinstance(binding.expr, Call) and binding.expr.name in deferred_dataflow_calls) or (
            _semantic_expr_names(binding.expr) & dataflow_scalar_results
        ):
            deferred_bindings.append(binding)
            continue
        value = _eval_expr(binding.expr, p)
        if isinstance(value, UserEntity):
            value.name = binding.name
            p.entities[binding.name] = value
        else:
            p._bindings[binding.name] = value
    for state_set in p.ast.state_sets:
        if state_set.name not in p._states:
            raise TypeError(f"unknown state '{state_set.name}'")
        p._states[state_set.name] = _eval_expr(state_set.expr, p)
    # Goal-oriented operations are now executed through the common GoalIR.
    # The planner is intentionally conservative: it supplies the semantic
    # dispatch boundary, while each kind keeps its verified reference strategy.
    execution_plan = build_execution_plan(p.ast)
    goal_irs = tuple(plan.goal for plan in execution_plan.goals)
    plan_by_result = {plan.goal.result: plan for plan in execution_plan.goals}
    graph_map = {g.name: g for g in p.ast.graphs}
    collections = {name:list(rows) for name, rows in (p.data_tables or {}).items()}
    for name, value in p._bindings.items():
        if isinstance(value, list):
            collections[name] = value
    # Keep the semantic collection namespace visible while mixed goals execute.
    p._collections = collections

    def execute_goal(g: GoalIR):
        plan = plan_by_result[g.result]
        strategy = plan.selected_strategy
        if strategy == "none":
            raise TypeError(f"no applicable execution strategy for goal '{g.result}'")
        if g.kind == "select":
            if g.source not in collections:
                return False
            source_value = collections[g.source]
            # A selected goal is a scalar semantic value. Treating it as a
            # one-element collection allows declarative goal chaining without
            # introducing a special source syntax.
            candidates = source_value if isinstance(source_value, list) else [source_value]
            if g.constraints:
                candidates = [row for row in candidates if bool(_eval_expr(g.constraints[0], p, row))]
            if not candidates:
                raise TypeError(f"choose '{g.result}' found no matching value")
            if strategy not in ("scan",):
                raise TypeError(f"reference runtime cannot execute select strategy {strategy!r}")
            if g.direction == "minimizing":
                collections[g.result] = min(candidates, key=lambda row: _eval_expr(g.key, p, row))
            else:
                collections[g.result] = max(candidates, key=lambda row: _eval_expr(g.key, p, row))
            return True

        if g.kind == "path":
            if g.source not in graph_map:
                raise TypeError(f"unknown graph '{g.source}'")
            graph = graph_map[g.source]
            if strategy not in ("dijkstra", "cost-aware search", "bidirectional-dijkstra"):
                raise TypeError(f"reference runtime cannot execute path strategy {strategy!r}")
            import heapq
            adj = {}
            for a,b,cost,bidir in graph.edges:
                adj.setdefault(a, []).append((b,cost))
                if bidir: adj.setdefault(b, []).append((a,cost))
            if g.start == g.end:
                collections[g.result] = GraphPath((g.start,), 0.0)
                return True
            heap=[(0.0, g.start, (g.start,))]; best={g.start:0.0}; found=None
            while heap:
                cost,node,path=heapq.heappop(heap)
                if cost != best.get(node): continue
                if node == g.end:
                    found=GraphPath(path,cost); break
                for nxt,w in adj.get(node, []):
                    nc=cost+w
                    if nc < best.get(nxt, float('inf')):
                        best[nxt]=nc; heapq.heappush(heap,(nc,nxt,path+(nxt,)))
            if found is None:
                raise TypeError(f"find path '{g.result}' found no path from {g.start} to {g.end}")
            collections[g.result] = found
            return True

        if g.kind == "satisfy":
            if strategy not in ("enumeration", "constraint-propagation"):
                raise TypeError(f"reference runtime cannot execute satisfy strategy {strategy!r}")
            import itertools
            from .goal_plan import propagate_integer_bounds
            names = [v[0] for v in g.variables]
            bounds = propagate_integer_bounds(g.variables, g.constraints) if strategy == "constraint-propagation" else {v[0]: [v[1], v[2]] for v in g.variables}
            if any(lo > hi for lo, hi in bounds.values()):
                raise TypeError(f"satisfy '{g.result}' found no solution")
            domains = [range(bounds[n][0], bounds[n][1] + 1) for n in names]
            solution = None
            for values in itertools.product(*domains):
                local = dict(zip(names, values))
                if all(bool(_eval_expr(c, p, local=local)) for c in g.constraints):
                    solution = local
                    break
            if solution is None:
                raise TypeError(f"satisfy '{g.result}' found no solution")
            collections[g.result] = solution
            return True

        raise TypeError(f"unsupported goal kind '{g.kind}'")

    # Execute goal operations that are already dependency-ready. Selection goals
    # remain in the semantic dataflow scheduler so they can consume filters/maps
    # that are produced later in this runtime phase.
    select_goals = [g for g in goal_irs if g.kind == "select"]
    goal_pending = [g for g in goal_irs if g.kind not in {"select", "transition"}]
    ready = []
    for g in goal_pending:
        plan = plan_by_result[g.result]
        if all(dep in collections for dep in plan.dependencies):
            ready.append(g)
        else:
            continue
    for g in ready:
        execute_goal(g)
        goal_pending.remove(g)

    # A sequence is a state generator. The initial state is the first element;
    # each following element is produced by the transition expression using `value`.
    for seq in p.ast.sequences:
        value = _eval_expr(seq.initial, p)
        generated = []
        for _ in range(seq.steps):
            generated.append(value)
            if seq.until is not None and bool(_eval_expr(seq.until, p, local={"value": value})):
                break
            if seq.target is not None:
                target = _eval_expr(seq.target, p, local={"value": value})
                candidates = [_eval_expr(expr, p, local={"value": value}) for expr in seq.candidates]
                constraints = seq.constraints or ((seq.constraint,) if seq.constraint is not None else ())
                if constraints:
                    candidates = [candidate for candidate in candidates if all(bool(_eval_expr(c, p, local={"value": value, "candidate": candidate})) for c in constraints)]
                    if not candidates:
                        break
                # Goal-directed transition: choose the legal next state that
                # minimizes distance to the target. Ties are resolved by the
                # source order of candidates, making the construct deterministic.
                value = min(candidates, key=lambda candidate: _goal_distance(candidate, target))
            else:
                value = _eval_expr(seq.expr, p, local={"value": value})
        collections[seq.result] = generated
    # The unified semantic execution graph is now the scheduler for the
    # declarative dataflow. Runtime semantics remain unchanged; the graph only
    # determines a dependency-safe execution order.
    from .semantic_graph import build_semantic_graph
    semantic_graph = build_semantic_graph(p.ast)
    all_operations = ([("filter", op) for op in p.ast.filters] +
                      [("sort", op) for op in p.ast.sorts] +
                      [("conditional_pipeline", op) for op in p.ast.conditional_pipelines] +
                      [("map", op) for op in p.ast.maps] +
                      [("aggregate", op) for op in p.ast.aggregates] +
                      [("reduce", op) for op in p.ast.reduces] +
                      [("goal_ir", g) for g in select_goals])
    # Match graph nodes to concrete runtime operations by semantic kind and
    # logical result. The graph carries versioned bindings, so repeated names
    # no longer require the legacy source-ordered fallback.
    op_queues = {}
    for kind, op in all_operations:
        op_queues.setdefault((kind, op.result), []).append(op)
    pending = []
    for binding in semantic_graph.topological_order():
        node = semantic_graph.by_binding()[binding]
        runtime_kind = "goal_ir" if node.kind in {"select", "goal:select"} else node.kind
        queue = op_queues.get((runtime_kind, node.result), [])
        if queue:
            pending.append((runtime_kind, queue.pop(0)))
    while pending:
        progress = False
        remaining = []
        for kind, op in pending:
            source = op.source
            fused_pipelines = getattr(p, "_optimization_fused_pipelines", {})
            fused_for = fused_pipelines.get(op.result) if kind == "map" else None
            fused_terminals = getattr(p, "_optimization_fused_terminals", {})
            fused_terminal_for = fused_terminals.get(op.result) if kind == "aggregate" else None
            if source not in collections and fused_for is None and fused_terminal_for is None:
                remaining.append((kind, op))
                continue
            if kind == "filter":
                # Fused terminal pipelines consume this semantic intermediate
                # directly from the source and therefore do not materialize it.
                fused_terminal_intermediates = getattr(p, "_optimization_fused_terminal_intermediates", set())
                if op.result in fused_terminal_intermediates:
                    continue
                # If this filter feeds a fused one-pass filter->map pipeline,
                # its semantic result is materialized only conceptually; the
                # final map operation performs the actual pass.
                if any(any(f.result == op.result for f in fused_filters) for _, fused_filters, _ in fused_pipelines.values()):
                    continue
                collections[op.result] = [row for row in collections[source]
                                           if bool(_eval_pipeline_expr(op.predicate.expr, p, row))]
            elif kind == "conditional_pipeline":
                cond=_eval_expr(op.condition,p)
                if not isinstance(cond,bool): raise TypeError("conditional pipeline condition must evaluate to Boolean")
                selected_stages=op.then_stages if cond else op.else_stages
                value=collections[source]
                for stage_kind, stage_expr in selected_stages:
                    if stage_kind == 'where':
                        value=[row for row in value if bool(_eval_pipeline_expr(stage_expr.expr,p,row))]
                    elif stage_kind == 'map':
                        value=[_eval_pipeline_expr(stage_expr,p,row) for row in value]
                    elif stage_kind == 'sort':
                        value=sorted(value,key=lambda row:_eval_pipeline_expr(stage_expr.expr,p,row),reverse=not stage_expr.ascending)
                    elif stage_kind == 'aggregate':
                        name,ex=stage_expr
                        vals=[_eval_pipeline_expr(ex,p,row) for row in value]
                        if name=='count':
                            value=len(vals)
                        elif not vals:
                            raise TypeError(f"aggregate '{name}' cannot operate on an empty collection")
                        elif name=='sum':
                            total=vals[0]
                            for v in vals[1:]: total=qadd(total,v) if isinstance(total,Quantity) else total+v
                            value=total
                        elif name=='max':
                            value=max(vals)
                        elif name=='min':
                            value=min(vals)
                        else:
                            total=vals[0]
                            for v in vals[1:]: total=qadd(total,v) if isinstance(total,Quantity) else total+v
                            value=qdiv(total,len(vals))
                    elif stage_kind == 'reduce':
                        acc=_eval_expr(stage_expr[0],p)
                        for item in value:
                            acc=_eval_expr(stage_expr[1],p,row=item,local={'acc':acc})
                        value=acc
                    else:
                        raise TypeError(f"unknown conditional pipeline operation '{stage_kind}'")
                collections[op.result]=value
            elif kind == "sort":
                collections[op.result] = sorted(collections[source],
                                                key=lambda row: _eval_pipeline_expr(op.spec.expr, p, row),
                                                reverse=not op.spec.ascending)
            elif kind == "map":
                fused_terminal_intermediates = getattr(p, "_optimization_fused_terminal_intermediates", set())
                if op.result in fused_terminal_intermediates:
                    continue
                aliases = getattr(p, "_optimization_identity_aliases", {})
                fused_pipelines = getattr(p, "_optimization_fused_pipelines", {})
                fused_pipeline = fused_pipelines.get(op.result)
                if fused_pipeline is not None:
                    base_source, filter_chain, map_chain = fused_pipeline
                    values = []
                    for row in collections[base_source]:
                        if all(bool(_eval_pipeline_expr(f.predicate.expr, p, row)) for f in filter_chain):
                            value = row
                            # Current optimizer records a single final map in
                            # this optimization. Keep the representation
                            # extensible so later passes can add more stages.
                            for map_stage in map_chain:
                                value = _eval_pipeline_expr(map_stage.expr, p, value)
                            values.append(value)
                    collections[op.result] = values
                elif aliases.get(op.result) == source:
                    collections[op.result] = collections[source]
                else:
                    fused = getattr(p, "_optimization_fused_intermediates", {}).get(op.result)
                    if fused is not None and fused[0] == source:
                        intermediate_name, intermediate_expr = fused[1], fused[2]
                        values = []
                        intermediate_values = []
                        for row in collections[source]:
                            mid = _eval_expr(intermediate_expr, p, row)
                            intermediate_values.append(mid)
                            values.append(_eval_pipeline_expr(op.expr, p, row))
                        collections[intermediate_name] = intermediate_values
                        collections[op.result] = values
                    else:
                        collections[op.result] = [_eval_pipeline_expr(op.expr, p, row) for row in collections[source]]
            elif kind == "aggregate":
                fused_terminals = getattr(p, "_optimization_fused_terminals", {})
                fused_terminal = fused_terminals.get(op.result)
                if fused_terminal is not None:
                    base_source, filter_chain, map_chain, terminal = fused_terminal
                    values = []
                    for row in collections[base_source]:
                        if not all(bool(_eval_pipeline_expr(f.predicate.expr, p, row)) for f in filter_chain):
                            continue
                        value = row
                        for map_stage in map_chain:
                            value = _eval_pipeline_expr(map_stage.expr, p, value)
                        values.append(_eval_pipeline_expr(op.expr, p, value))
                    if not values:
                        raise TypeError(f"aggregate '{op.operation}' cannot operate on an empty collection")
                    if op.operation == "sum":
                        total = values[0]
                        for value in values[1:]:
                            total = qadd(total, value) if isinstance(total, Quantity) else total + value
                        collections[op.result] = total
                    elif op.operation == "max":
                        collections[op.result] = max(values)
                    elif op.operation == "min":
                        collections[op.result] = min(values)
                    else:
                        total = values[0]
                        for value in values[1:]:
                            total = qadd(total, value) if isinstance(total, Quantity) else total + value
                        collections[op.result] = qdiv(total, len(values))
                else:
                    values = [_eval_pipeline_expr(op.expr, p, row) for row in collections[source]]
                if fused_terminal is not None:
                    pass
                elif op.operation == "count":
                    collections[op.result] = len(values)
                elif not values:
                    raise TypeError(f"aggregate '{op.operation}' cannot operate on an empty collection")
                elif op.operation == "sum":
                    total = values[0]
                    for value in values[1:]:
                        total = qadd(total, value) if isinstance(total, Quantity) else total + value
                    collections[op.result] = total
                elif op.operation == "max":
                    collections[op.result] = max(values)
                elif op.operation == "min":
                    collections[op.result] = min(values)
                elif op.operation in ("average", "avg"):
                    total = values[0]
                    for value in values[1:]:
                        total = qadd(total, value) if isinstance(total, Quantity) else total + value
                    collections[op.result] = qdiv(total, len(values))
            elif kind == "reduce":
                accumulator = _eval_expr(op.initial, p)
                for item in collections[source]:
                    accumulator = _eval_expr(op.expr, p, row=item, local={"acc": accumulator})
                collections[op.result] = accumulator
            elif kind == "goal_ir":
                if op.source not in collections:
                    remaining.append((kind, op))
                    continue
                execute_goal(op)
            progress = True
        if not progress:
            unresolved = ", ".join(op.result for _, op in remaining)
            raise TypeError(f"cannot resolve collection operations: {unresolved}")
        pending = remaining

    # Grouped aggregate calls are terminal dataflow expressions represented
    # as bindings rather than legacy AggregateOp nodes. Resolve them only after
    # their source collections have been materialized, so a pipeline such as
    # read_csv -> where -> map -> group_sum is executable by the reference
    # interpreter as well as by the native backend.
    if deferred_bindings:
        p._collections = collections
        # Resolve ordinary scalar bindings that depend on aggregate/reduce
        # results before evaluating grouped terminal calls. Keep declaration
        # order and repeat while progress is possible to support dependencies
        # between deferred scalar bindings.
        grouped_bindings = []
        scalar_pending = []
        for binding in deferred_bindings:
            if isinstance(binding.expr, Call) and binding.expr.name in deferred_dataflow_calls:
                grouped_bindings.append(binding)
            else:
                scalar_pending.append(binding)
        while scalar_pending:
            remaining_scalar = []
            progressed_scalar = False
            for binding in scalar_pending:
                try:
                    value = _eval_expr(binding.expr, p)
                except TypeError as exc:
                    if "unknown value" in str(exc):
                        remaining_scalar.append(binding)
                        continue
                    raise
                if isinstance(value, UserEntity):
                    value.name = binding.name
                    p.entities[binding.name] = value
                else:
                    p._bindings[binding.name] = value
                    if isinstance(value, list):
                        collections[binding.name] = value
                progressed_scalar = True
            if not progressed_scalar and remaining_scalar:
                names = ", ".join(binding.name for binding in remaining_scalar)
                raise TypeError(f"cannot resolve bindings depending on dataflow results: {names}")
            scalar_pending = remaining_scalar
        # Grouped terminal bindings share a source/key in common analytical
        # workloads. Build the stable groups once and derive all requested
        # metrics from that materialization instead of repeating the grouping
        # scan for every group_* call. The fallback keeps arbitrary call shapes
        # on the ordinary reference evaluator.
        from .stdlib.aggregate import _groups as _aggregate_groups
        grouped_cache = {}
        for binding in grouped_bindings:
            call = binding.expr
            value = None
            if call.name in deferred_dataflow_calls and call.args and isinstance(call.args[0], Name):
                source_name = call.args[0].name
                if source_name in collections and len(call.args) >= 2:
                    key_value = _eval_expr(call.args[1], p)
                    cache_key = (source_name, key_value)
                    if cache_key not in grouped_cache:
                        grouped_cache[cache_key] = _aggregate_groups(collections[source_name], key_value)
                    groups = grouped_cache[cache_key]
                    if call.name == "group_by":
                        value = [{"key": g["key"], "items": g["items"]} for g in groups]
                    elif call.name == "group_count":
                        value = [{"key": g["key"], "count": len(g["items"])} for g in groups]
                    elif len(call.args) == 3:
                        value_key = _eval_expr(call.args[2], p)
                        out=[]
                        for g in groups:
                            values=[row.get(value_key) for row in g["items"]]
                            if not all(isinstance(x,(int,float)) and not isinstance(x,bool) for x in values):
                                raise TypeError(f"{call.name} value field must contain Number values")
                            if call.name == "group_sum": metric_name, metric_value = "sum", sum(values)
                            elif call.name == "group_average": metric_name, metric_value = "average", sum(values)/len(values)
                            elif call.name == "group_min": metric_name, metric_value = "min", min(values)
                            else: metric_name, metric_value = "max", max(values)
                            out.append({"key": g["key"], metric_name: metric_value})
                        value = out
            if value is None:
                value = _eval_expr(call, p)
            p._bindings[binding.name] = value
            if isinstance(value, list):
                collections[binding.name] = value

    # Selection goals have now been materialized by the semantic dataflow.
    # Execute any remaining path/satisfy goals whose dependencies became
    # available through that dataflow, preserving GoalIR dependency order.
    while goal_pending:
        progressed = False
        remaining_goals = []
        for g in goal_pending:
            plan = plan_by_result[g.result]
            if any(dep not in collections for dep in plan.dependencies):
                remaining_goals.append(g)
                continue
            execute_goal(g)
            progressed = True
        if not progressed:
            blocked = ", ".join(g.result for g in remaining_goals)
            raise TypeError(f"unresolved goal dependencies: {blocked}")
        goal_pending = remaining_goals
    if collections:
        p._collections = collections
        all_results = [q.result for q in p.ast.sequences] + [f.result for f in p.ast.filters] + [s.result for s in p.ast.sorts] + [m.result for m in p.ast.maps] + [a.result for a in p.ast.aggregates] + [r.result for r in p.ast.reduces] + [g.result for g in p.ast.goals] + [g.result for g in p.ast.path_goals] + [g.result for g in p.ast.satisfy_goals]
        if all_results:
            last = all_results[-1]
            p._data_result_name = last
            p._data_result = collections[last]
    if p.circles:
        p._circle_results = {}
        for c in p.circles:
            p._circle_results[(c.name,"area")]=Quantity(math.pi*c.radius.value*c.radius.value,"m2")
            p._circle_results[(c.name,"circumference")]=Quantity(2*math.pi*c.radius.value,"m")
    if p.simulation:
        target_name, attractor_name, duration, step=p.simulation
        by={b.name:b for b in p.bodies}; target=by[target_name]; attractor=by[attractor_name]
        steps=int(math.floor(duration/step + 1e-12)); remainder=duration-steps*step
        G=6.67430e-11
        for k in range(steps + (1 if remainder>1e-12 else 0)):
            dt=step if k<steps else remainder
            r=target.fields["position"]; v=target.fields["velocity"]; m=attractor.fields["mass"]
            a=G*m.value/(r.value*r.value)
            target.fields["velocity"]=Quantity(v.value+a*dt,"mps")
            target.fields["position"]=Quantity(r.value+target.fields["velocity"].value*dt,"m")
    # Execute source-ordered top-level show/if statements after declarative
    # bindings and collection operations have been materialized. Block-local
    # `let` declarations do not leak outside their branch.
    if p.ast.top_level_statements and any(isinstance(stmt, IfOp) for stmt in p.ast.top_level_statements):
        emitted = []
        def execute_top_level(statements, inherited_scope=None):
            scope = dict(inherited_scope or {})
            for statement in statements:
                if isinstance(statement, LetOp):
                    if statement.name in scope:
                        raise TypeError(f"duplicate local variable '{statement.name}'")
                    scope[statement.name] = _eval_expr(statement.expr, p, local=scope)
                elif isinstance(statement, LocalCollectionOp):
                    if statement.name in scope:
                        raise TypeError(f"duplicate local variable '{statement.name}'")
                    source_value = scope.get(statement.source)
                    if source_value is None:
                        source_value = _eval_expr(Name(statement.source), p, local=scope)
                    scope[statement.name] = _execute_local_collection(source_value, statement.stages, p, scope)
                elif isinstance(statement, ShowOp):
                    if scope:
                        emitted.append(Literal(_eval_expr(statement.target, p, local=scope)))
                    else:
                        emitted.append(statement.target)
                elif isinstance(statement, IfOp):
                    condition = _eval_expr(statement.condition, p, local=scope)
                    if not isinstance(condition, bool):
                        raise TypeError("if condition must evaluate to Boolean")
                    branch = statement.then_body if condition else statement.else_body
                    execute_top_level(branch, scope)
                else:
                    raise TypeError(f"unsupported top-level statement {type(statement).__name__}")
        execute_top_level(p.ast.top_level_statements)
        p.show_exprs = emitted
        # Avoid the legacy output path printing statically collected shows from
        # branches that were not selected at runtime.
        p.shows = []
    return p

def show_value(p:Program, n:str, f:str):
    if n in getattr(p, '_bindings', {}):
        return show_expr_value(p, Name(n))
    if n in (p.entities or {}):
        value=p.entities[n]
        if f=='__value__':
            return str(value.fields)
        return str(value.fields[f])
    if n in getattr(p, '_collections', {}):
        rows=p._collections[n]
        if isinstance(rows, dict):
            if 'name' not in rows:
                return '{' + ', '.join(f'{k}={v}' for k,v in rows.items()) + '}'
            rest=", ".join(f"{k}={v}" for k,v in rows.items() if k != 'name')
            return f"{rows.get('name','row')}({rest})"
        parts=[]
        for r in rows:
            if isinstance(r, dict):
                if set(r.keys()) == {"name", "age"}:
                    parts.append(f"{r.get('name','row')}({r['age']})")
                else:
                    rest=", ".join(f"{k}={v}" for k,v in r.items() if k != "name")
                    parts.append(f"{r.get('name','row')}({rest})")
            else:
                parts.append(f"{r.name}({r.age})")
        return "[" + ", ".join(parts) + "]"
    if hasattr(p,"_circle_results") and (n,f) in p._circle_results:
        q=p._circle_results[(n,f)]; return f"{q.value:.15g} {q.unit}"
    q=next(b for b in p.bodies if b.name==n).fields[f]
    return f"{q.value:.15g} {q.unit}"


def mlir(p:Program):
    """Lower the high-level gravity simulation to standard textual MLIR.

    The simulation loop is represented with scf.for and scalar arithmetic with
    arith. This is a compiler lowering, not an unrolled dump of every timestep.
    """
    validate(p)
    t,a,duration,step=p.simulation
    by={b.name:b for b in p.bodies}
    tb,ab=by[t],by[a]
    x=tb.fields["position"].value
    v=tb.fields["velocity"].value
    m=ab.fields["mass"].value
    G=6.67430e-11
    steps=int(math.floor(duration/step + 1e-12))
    remainder=duration-steps*step
    def c(v): return f"0x{struct.unpack('Q', struct.pack('d', float(v)))[0]:016X}"
    out=["module {", '  func.func @simulate() -> (f64, f64) {',
         f"    %x0 = arith.constant {c(x)} : f64",
         f"    %v0 = arith.constant {c(v)} : f64",
         f"    %mass = arith.constant {c(m)} : f64",
         f"    %G = arith.constant {c(G)} : f64",
         f"    %dt = arith.constant {c(step)} : f64",
         f"    %zero = arith.constant 0 : index",
         f"    %steps = arith.constant {steps} : index",
         f"    %one = arith.constant 1 : index",
         "    %xf, %vf = scf.for %i = %zero to %steps step %one iter_args(%x = %x0, %v = %v0) -> (f64, f64) {",
         "      %xx = arith.mulf %x, %x : f64",
         "      %gm = arith.mulf %G, %mass : f64",
         "      %acc = arith.divf %gm, %xx : f64",
         "      %dv = arith.mulf %acc, %dt : f64",
         "      %vn = arith.addf %v, %dv : f64",
         "      %dx = arith.mulf %vn, %dt : f64",
         "      %xn = arith.addf %x, %dx : f64",
         "      scf.yield %xn, %vn : f64, f64",
         "    }"]
    curx,curv="%xf","%vf"
    if remainder>1e-12:
        out += [f"    %rem = arith.constant {c(remainder)} : f64",
                f"    %xxr = arith.mulf {curx}, {curx} : f64",
                f"    %gmr = arith.mulf %G, %mass : f64",
                f"    %accr = arith.divf %gmr, %xxr : f64",
                f"    %dvr = arith.mulf %accr, %rem : f64",
                f"    %vr = arith.addf {curv}, %dvr : f64",
                f"    %dxr = arith.mulf %vr, %rem : f64",
                f"    %xr = arith.addf {curx}, %dxr : f64"]
        curx,curv="%xr","%vr"
    out += [f"    func.return {curx}, {curv} : f64, f64", "  }"]
    out += ['  func.func @main() {', '    %pos, %vel = func.call @simulate() : () -> (f64, f64)']
    for n,f in p.shows:
        if n==t and f=="position": out.append('    func.call @slang_show_f64(%pos) : (f64) -> ()')
        elif n==t and f=="velocity": out.append('    func.call @slang_show_f64(%vel) : (f64) -> ()')
    out += ["    func.return", "  }", '  func.func private @slang_show_f64(%value: f64)', "}"]
    return "\n".join(out)

def execution_ir(p:Program):
    validate(p)
    from .execution_ir import build_execution_ir, format_execution_ir
    return format_execution_ir(build_execution_ir(p.ast))

def memory_regions(p:Program):
    validate(p)
    from .execution_ir import build_execution_ir
    return build_execution_ir(p.ast)


def alias_analysis(p:Program):
    validate(p)
    from .execution_ir import build_execution_ir
    from .alias_analysis import format_alias_analysis
    return format_alias_analysis(build_execution_ir(p.ast))


def conflict_graph(p:Program):
    validate(p)
    from .execution_ir import build_execution_ir
    from .conflict_graph import format_conflict_graph
    return format_conflict_graph(build_execution_ir(p.ast))


def dependency_graph(p:Program):
    validate(p)
    from .execution_ir import build_execution_ir
    from .execution_ir import build_execution_ir
    from .dependency_graph import build_dependency_graph, format_dependency_graph
    return format_dependency_graph(build_dependency_graph(build_execution_ir(p.ast)))

def dependency_analysis(p:Program):
    validate(p)
    from .execution_ir import build_execution_ir
    from .dependency_analysis import analyze_dependency_graph, format_dependency_analysis
    ir = build_execution_ir(p.ast)
    return format_dependency_analysis(analyze_dependency_graph(ir))

def optimize_execution_ir(p:Program):
    from .execution_ir import build_execution_ir
    from .execution_optimizer import optimize_execution_ir as _optimize
    ir_obj = build_execution_ir(p.ast)
    optimized, report = _optimize(ir_obj)
    return optimized, report

def runtime_execute(p:Program, execution_profile=None, max_events=None, max_duration_ms=None):
    """Execute through the plan-aware runtime boundary with optional execution limits."""
    from .runtime import execute
    return execute(
        p,
        execution_profile=execution_profile,
        max_events=max_events,
        max_duration_ms=max_duration_ms,
    )


def selected_execution_plan(p:Program):
    validate(p)
    from .compiler_pipeline import compile_semantic_pipeline
    from .selected_execution_plan import format_selected_execution_plan
    return format_selected_execution_plan(compile_semantic_pipeline(p.ast).selected_execution_plan)


def execution_explain(p:Program):
    validate(p)
    from .compiler_pipeline import compile_semantic_pipeline
    from .explainability import format_execution_explanation
    return format_execution_explanation(compile_semantic_pipeline(p.ast).execution_explanation)


def effect_analysis(p:Program):
    validate(p)
    from .compiler_pipeline import compile_semantic_pipeline
    from .effect_analysis import format_effect_analysis
    return format_effect_analysis(compile_semantic_pipeline(p.ast).effects)


def function_effect_analysis(p:Program):
    validate(p)
    from .compiler_pipeline import compile_semantic_pipeline
    from .function_effects import format_function_effects
    return format_function_effects(compile_semantic_pipeline(p.ast).function_effects)


def higher_order_effect_analysis(p:Program):
    validate(p)
    from .compiler_pipeline import compile_semantic_pipeline
    from .higher_order_effects import format_higher_order_effects
    return format_higher_order_effects(compile_semantic_pipeline(p.ast).higher_order_effects)


def compiler_pipeline(p:Program):
    validate(p)
    from .compiler_pipeline import compile_semantic_pipeline
    return compile_semantic_pipeline(p.ast)


def execution_plan(p:Program):
    validate(p)
    from .execution_ir import build_execution_ir
    from .execution_plan import build_execution_plan, format_execution_plan
    ir = build_execution_ir(p.ast)
    return format_execution_plan(build_execution_plan(ir))


def strategy_selection(p:Program):
    validate(p)
    from .execution_ir import build_execution_ir
    from .execution_plan import build_execution_plan
    from .strategy_selection import build_strategy_choices, format_strategy_choices
    ir = build_execution_ir(p.ast)
    plan = build_execution_plan(ir)
    return format_strategy_choices(build_strategy_choices(plan, ir))


def cost_analysis(p:Program):
    validate(p)
    from .execution_ir import build_execution_ir
    from .execution_plan import build_execution_plan
    from .strategy_selection import cost_analysis
    ir = build_execution_ir(p.ast)
    plan = build_execution_plan(ir)
    return cost_analysis(plan, ir)

def execution_schedule(p:Program):
    validate(p)
    from .execution_ir import build_execution_ir
    from .execution_scheduler import build_schedule, format_schedule
    return format_schedule(build_schedule(build_execution_ir(p.ast)))


def goal_ir(p:Program):
    """Lower all goal-oriented source operations to the unified Goal IR."""
    validate(p)
    return format_goal_ir(lower_goals(p.ast))


def ir(p:Program):
    validate(p)
    out=["module {", "  slang.physics gravity",]
    for b in p.bodies:
        out.append(f"  %body_{b.name} = slang.make_body \"{b.name}\"")
        for f,q in b.fields.items(): out.append(f"    slang.set_field %body_{b.name}, \"{f}\", {q.value:g} {q.unit}")
    t,a,d,s=p.simulation
    out.append(f"  slang.simulate_gravity %body_{t}, %body_{a}, duration={d:g} s, step={s:g} s, integrator=explicit_euler")
    for n,f in p.shows: out.append(f"  slang.show_field %body_{n}, \"{f}\"")
    out.append("}"); return "\n".join(out)


def _reduce_binary_op(expr):
    """Return runtime ABI opcode for the supported numeric reduce recurrence."""
    if not isinstance(expr, Binary):
        return None
    # The 0.83 native ABI intentionally supports only accumulator/current-value
    # arithmetic. More complex expressions remain interpreter/backend territory.
    if not (isinstance(expr.left, Name) and expr.left.name == "acc"):
        return None
    if not (isinstance(expr.right, Field) and isinstance(expr.right.base, Name) and expr.right.base.name == "row"):
        return None
    if expr.op not in {"+", "-", "*", "/"}:
        return None
    return {"+": 0, "-": 1, "*": 2, "/": 3}[expr.op], expr.right.name


def reduce_llvm_ir(p:Program):
    """Emit LLVM IR using the 0.83 numeric-reduce runtime ABI.

    The ABI is intentionally small and explicit: a contiguous f64 buffer,
    element count, initial accumulator and a deterministic operation code.
    """
    validate(p)
    if not p.ast.reduces:
        raise ValueError("reduce LLVM backend requires at least one reduce operation")
    if p.bodies or p.simulation or p.ast.filters or p.ast.maps or p.ast.sorts:
        raise ValueError("reduce LLVM backend currently accepts reduce-only programs")
    tables = p.data_tables or {}
    arrays=[]
    calls=[]
    shown=[]
    for red in p.ast.reduces:
        rows=tables.get(red.source)
        if rows is None:
            raise ValueError(f"reduce source '{red.source}' is not a data table")
        if not isinstance(red.initial, Literal) or not isinstance(red.initial.value, (int,float)):
            raise ValueError("native reduce requires a numeric literal initial accumulator")
        info=_reduce_binary_op(red.expr)
        if info is None:
            raise ValueError("native reduce supports only 'acc <+|-|*|/> row.<field>'")
        opcode, field=info
        values=[]
        for row in rows:
            value=row.get(field)
            if not isinstance(value,(int,float)):
                raise ValueError(f"reduce field '{field}' in '{red.source}' must be numeric")
            values.append(float(value))
        arrays.append((red.result, values))
        calls.append((red.result, len(values), float(red.initial.value), opcode))
    def c(v):
        return f"0x{struct.unpack('Q', struct.pack('d', float(v)))[0]:016X}"
    lines=['; ModuleID = \'slang-reduce\'', 'source_filename = "slang"', '']
    for idx,(name,values) in enumerate(arrays):
        elems=', '.join(f'double {c(v)}' for v in values) or 'double 0.000000e+00'
        lines.append(f'@data_{idx} = private constant [{len(values) if values else 1} x double] [{elems}]')
    lines += ['', 'declare double @slang_reduce_f64(ptr, i64, double, i32)', 'declare i32 @printf(ptr, ...)', '']
    for i,(name,_) in enumerate(arrays):
        fmt=f'@fmt_{i}'
        text=f'{name} = %.15g\\0A\\00'
        lines.append(f'{fmt} = private constant [{len(name)+10} x i8] c"{text}"')
    lines += ['', 'define i32 @main() {', 'entry:']
    for i,(name,n,initial,opcode) in enumerate(calls):
        lines.append(f'  %{name} = call double @slang_reduce_f64(ptr getelementptr inbounds ([{n if n else 1} x double], ptr @data_{i}, i64 0, i64 0), i64 {n}, double {c(initial)}, i32 {opcode})')
        if any(isinstance(x, Name) and x.name==name for x in p.show_exprs) or any(isinstance(x, Name) and x.name==name for x in [show.target for show in p.ast.shows]):
            lines.append(f'  %print_{i} = call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([{len(name)+10} x i8], ptr @fmt_{i}, i64 0, i64 0), double %{name})')
    lines += ['  ret i32 0', '}', '']
    return '\n'.join(lines)


def _numeric_collection_expr(expr, field_ptr="%value"):
    """Lower a restricted scalar collection expression to LLVM f64 text.

    The native 0.84 collection backend deliberately accepts only numeric
    literals, row fields and arithmetic combinations of them.  This keeps the
    lowering exact rather than pretending arbitrary S-Lang expressions are
    LLVM-lowerable.
    """
    if isinstance(expr, Literal) and isinstance(expr.value, (int, float)):
        return f"{float(expr.value):.17e}"
    if isinstance(expr, (Field, Property)) and isinstance(expr.base, Name) and expr.base.name == "row":
        return f"load double, ptr {field_ptr}"
    if isinstance(expr, Name) and expr.name == "item":
        return f"load double, ptr {field_ptr}"
    if isinstance(expr, Binary) and expr.op in {"+", "-", "*", "/", "%"}:
        a = _numeric_collection_expr(expr.left, field_ptr)
        b = _numeric_collection_expr(expr.right, field_ptr)
        op = {"+":"fadd", "-":"fsub", "*":"fmul", "/":"fdiv", "%":"frem"}[expr.op]
        return f"{op} double {a}, {b}"
    raise ValueError("native collection backend supports numeric field/item arithmetic only")


def _collection_predicate(expr, field_ptr="%value"):
    if not isinstance(expr, Compare) or expr.op not in {">", ">=", "<", "<=", "==", "!="}:
        raise ValueError("native filter backend supports a single numeric comparison")
    a = _numeric_collection_expr(expr.left, field_ptr)
    b = _numeric_collection_expr(expr.right, field_ptr)
    pred = {">":"ogt", ">=":"oge", "<":"olt", "<=":"ole", "==":"oeq", "!=":"one"}[expr.op]
    return f"fcmp {pred} double {a}, {b}"


def _llvm_scalar_expr(expr, field_ptr, lines, serial, signatures=None, field_values=None):
    """Lower a numeric scalar expression to LLVM f64/i1 values.

    ``field_values`` maps ``row.<field>`` references to already-loaded LLVM
    SSA values for the current row.  ``item``/``value`` continue to denote
    the scalar value of an intermediate numeric collection.
    """
    field_values = field_values or {}
    if isinstance(expr, Literal) and isinstance(expr.value, (int,float)) and not isinstance(expr.value, bool):
        return f"{float(expr.value):.17e}"
    if isinstance(expr, (Field, Property)) and isinstance(expr.base, Name) and expr.base.name == "row":
        if expr.name in field_values:
            return field_values[expr.name]
        raise ValueError(f"native collection backend cannot resolve row field '{expr.name}' in this pipeline stage")
    if isinstance(expr, Name) and expr.name in {"item", "value"}:
        if expr.name in field_values:
            return field_values[expr.name]
        if field_ptr is None:
            raise ValueError("native collection backend cannot resolve scalar item/value at this stage")
        return f"%value{serial}"
    if isinstance(expr, Call) and signatures and expr.name in signatures:
        params, result = signatures[expr.name]
        if result != "double" or len(params) != len(expr.args) or any(t != "double" for t in params):
            raise ValueError(f"native collection call '{expr.name}' requires a Number -> Number function")
        vals=[_llvm_scalar_expr(a, field_ptr, lines, serial, signatures, field_values) for a in expr.args]
        name=f"%call{serial}_{len(lines)}"
        lines.append(f"  {name} = call double @{expr.name}({', '.join('double '+v for v in vals)})")
        return name
    if isinstance(expr, Binary) and expr.op in {"+","-","*","/","^","%"}:
        left=_llvm_scalar_expr(expr.left, field_ptr, lines, serial, signatures, field_values)
        right=_llvm_scalar_expr(expr.right, field_ptr, lines, serial, signatures, field_values)
        name=f"%expr{serial}_{len(lines)}"
        if expr.op == "^":
            lines.append(f"  {name} = call double @llvm.pow.f64(double {left}, double {right})")
        else:
            op={"+":"fadd","-":"fsub","*":"fmul","/":"fdiv","%":"frem"}[expr.op]
            lines.append(f"  {name} = {op} double {left}, {right}")
        return name
    if isinstance(expr, Compare) and expr.op in {">",">=","<","<=","==","!="}:
        left=_llvm_scalar_expr(expr.left, field_ptr, lines, serial, signatures, field_values)
        right=_llvm_scalar_expr(expr.right, field_ptr, lines, serial, signatures, field_values)
        name=f"%cmp{serial}_{len(lines)}"
        pred={">":"ogt",">=":"oge","<":"olt","<=":"ole","==":"oeq","!=":"one"}[expr.op]
        lines.append(f"  {name} = fcmp {pred} double {left}, {right}")
        return name
    if isinstance(expr, Logical):
        if expr.op == "not":
            value=_llvm_scalar_expr(expr.left, field_ptr, lines, serial, signatures, field_values)
            name=f"%not{serial}_{len(lines)}"
            lines.append(f"  {name} = xor i1 {value}, true")
            return name
        if expr.op in {"and","or"}:
            left=_llvm_scalar_expr(expr.left, field_ptr, lines, serial, signatures, field_values)
            right=_llvm_scalar_expr(expr.right, field_ptr, lines, serial, signatures, field_values)
            name=f"%logic{serial}_{len(lines)}"
            lines.append(f"  {name} = {expr.op} i1 {left}, {right}")
            return name
    if isinstance(expr, Conditional):
        condition=_llvm_collection_predicate(expr.condition, lines, serial, signatures, field_values)
        then_value=_llvm_scalar_expr(expr.then_expr, field_ptr, lines, serial, signatures, field_values)
        else_value=_llvm_scalar_expr(expr.else_expr, field_ptr, lines, serial, signatures, field_values)
        name=f"%select{serial}_{len(lines)}"
        lines.append(f"  {name} = select i1 {condition}, double {then_value}, double {else_value}")
        return name
    raise ValueError("native collection backend supports numeric arithmetic, comparisons, logical expressions and conditionals")

def _llvm_collection_predicate(expr, lines, serial, signatures=None, field_values=None):
    field_values = field_values or {}
    if isinstance(expr, Literal) and isinstance(expr.value, bool):
        return "true" if expr.value else "false"
    if isinstance(expr, Logical):
        if expr.op == "not":
            value = _llvm_collection_predicate(expr.left, lines, serial, signatures, field_values)
            name = f"%prednot{serial}_{len(lines)}"
            lines.append(f"  {name} = xor i1 {value}, true")
            return name
        if expr.op in {"and", "or"}:
            left = _llvm_collection_predicate(expr.left, lines, serial, signatures, field_values)
            right = _llvm_collection_predicate(expr.right, lines, serial, signatures, field_values)
            name = f"%predlogic{serial}_{len(lines)}"
            op = "and" if expr.op == "and" else "or"
            lines.append(f"  {name} = {op} i1 {left}, {right}")
            return name
        raise ValueError(f"native filter backend does not support logical operator '{expr.op}'")
    if isinstance(expr, Call) and signatures and expr.name in signatures:
        params, result = signatures[expr.name]
        if result != "i1" or len(params) != len(expr.args) or any(t != "double" for t in params):
            raise ValueError(f"native filter call '{expr.name}' requires a Number -> Boolean function")
        vals=[_llvm_scalar_expr(a, None, lines, serial, signatures, field_values) for a in expr.args]
        name=f"%predcall{serial}_{len(lines)}"
        lines.append(f"  {name} = call i1 @{expr.name}({', '.join('double '+v for v in vals)})")
        return name
    if not isinstance(expr, Compare) or expr.op not in {">",">=","<","<=","==","!="}:
        raise ValueError("native filter backend supports numeric comparisons, Boolean function calls, and logical combinations")
    left=_llvm_scalar_expr(expr.left, None, lines, serial, signatures, field_values)
    right=_llvm_scalar_expr(expr.right, None, lines, serial, signatures, field_values)
    pred={">":"ogt",">=":"oge","<":"olt","<=":"ole","==":"oeq","!=":"one"}[expr.op]
    name=f"%pred{serial}_{len(lines)}"
    lines.append(f"  {name} = fcmp {pred} double {left}, {right}")
    return name


def collection_llvm_ir(p:Program, function_part=None, signatures=None, schema_contract=None):
    """Lower numeric filter/map pipelines to real LLVM control flow."""
    validate(p)
    if p.bodies or p.simulation or p.ast.reduces or p.ast.sorts or p.ast.aggregates:
        raise ValueError("native collection backend currently accepts data/filter/map programs")
    if signatures is None:
        signatures = {}
    if not p.ast.filters and not p.ast.maps:
        raise ValueError("native collection backend requires filter or map operations")
    tables=p.data_tables or {}
    # 1.10.38: build the backend field-storage table from the semantic schema
    # contract once.  Lowering resolves row.<field> through this table rather
    # than rediscovering field types from AST record declarations.
    schema_by_binding={}
    for binding, in_schema, out_schema in (schema_contract or getattr(p, "_backend_schema_contract", ())):
        schema_by_binding[binding]=(in_schema, out_schema)
    def schema_fields(binding):
        pair=schema_by_binding.get(binding)
        if pair is None:
            matches=[v for k,v in schema_by_binding.items() if k.split("#",1)[0]==binding]
            if len(matches)==1: pair=matches[0]
        schema=pair[1] if pair else None
        if schema is None: return None
        return {f.name:f.type_name for f in getattr(schema,"fields",())}
    ordered=[]; available=set(tables); remaining=list(p.ast.filters)+list(p.ast.maps)
    while remaining:
        progress=False
        for op in remaining[:]:
            if op.source in available:
                ordered.append(op); available.add(op.result); remaining.remove(op); progress=True
        if not progress: raise ValueError("native collection backend requires a forward acyclic pipeline")

    def row_fields(expr):
        out=[]
        def walk(e):
            if isinstance(e,(Field,Property)) and isinstance(e.base,Name) and e.base.name=="row":
                if e.name not in out: out.append(e.name)
            elif isinstance(e,(Binary,Compare,Logical)):
                walk(e.left)
                if getattr(e,"right",None) is not None: walk(e.right)
            elif isinstance(e,Conditional):
                walk(e.condition); walk(e.then_expr); walk(e.else_expr)
            elif isinstance(e,Call):
                for arg in e.args: walk(arg)
        walk(expr)
        return out

    # Discover every row field needed from each concrete source table.  Filter
    # stages preserve record structure, so downstream stages can continue to
    # address row.<field>. Map stages intentionally produce scalar collections.
    source_fields={}
    stage_fields={}
    for op in ordered:
        expr=op.predicate.expr if isinstance(op,FilterOp) else op.expr
        fields=row_fields(expr)
        if op.source in tables:
            bucket=source_fields.setdefault(op.source,[])
            declared=schema_fields(op.source)
            if declared is not None:
                # Schema order is authoritative for storage layout.  Only
                # numeric fields are materialized by this numeric backend.
                for field, typ in declared.items():
                    if typ in {"Number", "Boolean"} and field not in bucket:
                        bucket.append(field)
                for field in fields:
                    if field not in declared:
                        raise ValueError(f"native collection schema contract for '{op.source}' has no field '{field}'")
                    if declared[field] not in {"Number", "Boolean"}:
                        raise ValueError(f"native collection field '{op.source}.row.{field}' has non-numeric type {declared[field]}")
                    if field not in bucket: bucket.append(field)
            else:
                for row in tables[op.source][:1]:
                    for field, value in row.items():
                        if isinstance(value,(int,float)) and not isinstance(value,bool) and field not in bucket:
                            bucket.append(field)
            for field in fields:
                if field not in bucket: bucket.append(field)
            source_stage_fields=list(bucket)
        else:
            source_stage_fields=list(stage_fields.get(op.source,[]))
            if fields:
                for field in fields:
                    if field not in source_stage_fields:
                        raise ValueError(f"native collection backend cannot resolve preserved row field '{field}' from '{op.source}'")
        if fields and not source_stage_fields:
            raise ValueError(f"native collection backend cannot preserve row fields through intermediate collection '{op.source}'")
        if isinstance(op,FilterOp):
            stage_fields[op.result]=source_stage_fields
        else:
            stage_fields[op.result]=[]
        if not fields and op.source in tables and op.source not in source_fields:
            numeric_fields=[]
            for fname in tables[op.source][0].keys() if tables[op.source] else []:
                if all(isinstance(row.get(fname),(int,float)) and not isinstance(row.get(fname),bool) for row in tables[op.source]):
                    numeric_fields.append(fname)
            if numeric_fields:
                source_fields[op.source]=[numeric_fields[0]]

    globals_=[]; source_info={}
    for source, fields in source_fields.items():
        if not fields:
            raise ValueError(f"native collection backend cannot find numeric fields for '{source}'")
        info={}
        for field in fields:
            vals=[]
            for row in tables[source]:
                v=row.get(field)
                if not isinstance(v,(int,float)) or isinstance(v,bool):
                    raise ValueError(f"native collection field '{field}' in '{source}' must be numeric")
                vals.append(float(v))
            gname=f"data_{source}_{field}".replace("-","_")
            globals_.append((gname,vals)); info[field]=(gname,len(vals))
        source_info[source]=info

    lines=["; ModuleID = 'slang-collection'", 'source_filename = "slang"', '']
    if function_part:
        lines.extend(function_part); lines.append('')
    for gname,vals in globals_:
        elems=', '.join(f'double {v:.17e}' for v in vals) or 'double 0.0'
        lines.append(f'@{gname} = private constant [{len(vals) if vals else 1} x double] [{elems}]')
    lines += ['', 'declare i32 @printf(ptr, ...)', 'declare double @llvm.pow.f64(double, double)', '@fmt = private constant [7 x i8] c"%.17g\\0A\\00"', '', 'define i32 @main() {', 'entry:']

    # Every stage has a scalar buffer. Filter stages additionally have one
    # buffer per preserved numeric field. This makes filtered records first-
    # class pipeline values instead of collapsing them to their first field.
    alloc={}
    for i,op in enumerate(ordered,1):
        src_cap = (next(iter(source_info[op.source].values()))[1]
                   if op.source in source_info else alloc[op.source][2]) or 1
        scalar_buf=f"%buf{i}"; count=f"%count{i}"
        field_bufs={}
        lines += [f"  {scalar_buf} = alloca [{src_cap} x double]", f"  {count} = alloca i64"]
        if isinstance(op,FilterOp):
            inherited = source_info.get(op.source, {}) if op.source in source_info else alloc[op.source][3]
            for field in inherited:
                fb=f"%buf{i}_{field}"
                field_bufs[field]=fb
                lines.append(f"  {fb} = alloca [{src_cap} x double]")
        alloc[op.result]=(scalar_buf,count,src_cap,field_bufs)
    lines += ['  br label %entry0', 'entry0:']

    # Descriptor: scalar pointer/count/capacity plus preserved field pointers.
    desc={}
    for source,info in source_info.items():
        primary=next(iter(info.values())); gname,n=primary
        ptr=f"getelementptr inbounds [{n if n else 1} x double], ptr @{gname}, i64 0, i64 0"
        fields={field:("global",fg,fn) for field,(fg,fn) in info.items()}
        desc[source]=(ptr,str(n),n,fields)
    for i,op in enumerate(ordered,1):
        buf,count,cap,field_bufs=alloc[op.result]
        if op.source in alloc:
            sb,sc,scp,sfields=alloc[op.source]
            fields={field:("buffer",fb,scp) for field,fb in sfields.items()}
            desc[op.source]=(f"getelementptr [{scp} x double], ptr {sb}, i64 0, i64 0",sc,scp,fields)

    current='entry0'
    for i,op in enumerate(ordered,1):
        buf,count,cap,out_fields=alloc[op.result]
        srcptr,srccount,src_cap,src_fields=desc[op.source]
        loop=f"loop{i}"; body=f"body{i}"; done=f"done{i}"; skip=f"skip{i}"
        lines += [f"  store i64 0, ptr {count}", f"  br label %{loop}", f"{loop}:", f"  %i{i} = phi i64 [ 0, %{current} ], [ %next{i}, %{skip} ]",
                  f"  %src_count{i} = add i64 0, {srccount}" if srccount.isdigit() else f"  %src_count{i} = load i64, ptr {srccount}",
                  f"  %cond{i} = icmp ult i64 %i{i}, %src_count{i}", f"  br i1 %cond{i}, label %{body}, label %{done}", f"{body}:"]
        lines.append(f"  %base{i} = {srcptr}" if srcptr.startswith("getelementptr") else f"  %base{i} = getelementptr inbounds ([1 x double], ptr null, i64 0, i64 0)")
        lines += [f"  %srcptr{i} = getelementptr double, ptr %base{i}, i64 %i{i}", f"  %value{i} = load double, ptr %srcptr{i}"]
        field_values={}
        for field,fielddesc in src_fields.items():
            value=f"%field{i}_{field}"
            if fielddesc[0] == "global":
                _, fg, fn = fielddesc
                lines.append(f"  %fieldbase{i}_{field} = getelementptr inbounds [{fn if fn else 1} x double], ptr @{fg}, i64 0, i64 0")
                fieldbase=f"%fieldbase{i}_{field}"
            else:
                _, fb, fn = fielddesc
                lines.append(f"  %fieldbase{i}_{field} = getelementptr [{fn} x double], ptr {fb}, i64 0, i64 0")
                fieldbase=f"%fieldbase{i}_{field}"
            lines += [f"  %fieldptr{i}_{field} = getelementptr double, ptr {fieldbase}, i64 %i{i}", f"  {value} = load double, ptr %fieldptr{i}_{field}"]
            field_values[field]=value
        if isinstance(op,FilterOp):
            keep=_llvm_collection_predicate(op.predicate.expr,lines,i,signatures,field_values)
            lines += [f"  br i1 {keep}, label %keepblock{i}, label %{skip}", f"keepblock{i}:", f"  %oc{i} = load i64, ptr {count}",
                      f"  %dst{i} = getelementptr [{cap} x double], ptr {buf}, i64 0, i64 %oc{i}", f"  store double %value{i}, ptr %dst{i}"]
            for field,fb in out_fields.items():
                srcfield=field_values.get(field)
                if srcfield is None:
                    raise ValueError(f"native filter backend cannot preserve field '{field}'")
                lines += [f"  %fdst{i}_{field} = getelementptr [{cap} x double], ptr {fb}, i64 0, i64 %oc{i}", f"  store double {srcfield}, ptr %fdst{i}_{field}"]
            lines += [f"  %on{i} = add i64 %oc{i}, 1", f"  store i64 %on{i}, ptr {count}", f"  br label %{skip}"]
        else:
            expr=_llvm_scalar_expr(op.expr,srcptr,lines,i,signatures,field_values)
            lines += [f"  %dst{i} = getelementptr [{cap} x double], ptr {buf}, i64 0, i64 %i{i}", f"  store double {expr}, ptr %dst{i}", f"  br label %{skip}"]
        lines += [f"{skip}:", f"  %next{i} = add i64 %i{i}, 1", f"  br label %{loop}", f"{done}:"]
        if isinstance(op,FilterOp):
            desc[op.result]=(f"getelementptr [{cap} x double], ptr {buf}, i64 0, i64 0",count,cap,
                              {field:("buffer",fb,cap) for field,fb in out_fields.items()})
        else:
            desc[op.result]=(f"getelementptr [{cap} x double], ptr {buf}, i64 0, i64 0", desc[op.source][1], cap, {})
        current=done

    show_names={x.name for x in (p.show_exprs or []) if isinstance(x,Name)}

    for j,(name,info) in enumerate(desc.items()):
        if name not in show_names: continue
        ptr,cnt,cap,_fields=info; loop=f"showloop{j}"; body=f"showbody{j}"; done=f"showdone{j}"; pred=current
        lines += [f"  br label %{loop}", f"{loop}:", f"  %si{j} = phi i64 [ 0, %{pred} ], [ %sn{j}, %{body} ]", f"  %show_count{j} = add i64 0, {cnt}" if cnt.isdigit() else f"  %show_count{j} = load i64, ptr {cnt}", f"  %show_cond{j} = icmp ult i64 %si{j}, %show_count{j}", f"  br i1 %show_cond{j}, label %{body}, label %{done}", f"{body}:", f"  %showbase{j} = {ptr}", f"  %sp{j} = getelementptr double, ptr %showbase{j}, i64 %si{j}", f"  %sv{j} = load double, ptr %sp{j}", f"  call i32 (ptr, ...) @printf(ptr @fmt, double %sv{j})", f"  %sn{j} = add i64 %si{j}, 1", f"  br label %{loop}", f"{done}:"]
        current=done
    lines += [f"  ret i32 0", '}']
    return '\n'.join(lines)


def _record_filter_scalar_sort_llvm_ir(p: Program, function_part=None, signatures=None):
    """Lower a Record filter followed by a scalar map and numeric sort.

    The Record filter must preserve every numeric field referenced by the
    scalar projection.  The projection then crosses into a one-dimensional
    scalar buffer; sorting and optional terminal aggregation operate on that
    buffer.  This is deliberately a small bridge rather than a second Record
    runtime representation.
    """
    signatures = signatures or {}
    if len(p.ast.sorts) != 1:
        raise ValueError("native Record scalar bridge requires exactly one sort")
    if len(p.ast.maps) != 1:
        raise ValueError("native Record scalar bridge requires exactly one scalar map")
    if len(p.ast.aggregates) > 1 or len(p.ast.reduces) > 1:
        raise ValueError("native Record scalar bridge supports at most one aggregate or reduce")
    from .ast import source_span_of
    def operation_position(op):
        span = source_span_of(op)
        return (span.start.line, span.start.column) if span else (10**9, 10**9)
    original_map = p.ast.maps[0]
    map_position = operation_position(original_map)
    original_pre_filters = [op for op in p.ast.filters if operation_position(op) < map_position]
    source = original_pre_filters[0].source if original_pre_filters else original_map.source

    # The source AST may intentionally rebind one public name at every stage.
    # Re-version the linear pipeline for this backend-local validation pass so
    # each filter sees the element type produced by its immediate predecessor.
    # This is internal SSA naming only; source syntax and diagnostics are unchanged.
    ordered_stages = sorted(
        list(p.ast.filters) + list(p.ast.maps) + list(p.ast.sorts),
        key=operation_position,
    )
    current_source = source
    renamed = {}
    final_public_name = ordered_stages[-1].result if ordered_stages else source
    for index, stage in enumerate(ordered_stages, 1):
        internal_result = final_public_name if index == len(ordered_stages) else f"__native_scalar_stage_{index}"
        renamed[id(stage)] = mark_source_span(
            replace(stage, source=current_source, result=internal_result),
            source_span_of(stage),
        )
        current_source = internal_result
    p.ast.filters = [renamed.get(id(op), op) for op in p.ast.filters]
    p.ast.maps = [renamed.get(id(op), op) for op in p.ast.maps]
    p.ast.sorts = [renamed.get(id(op), op) for op in p.ast.sorts]
    p.ast.reduces = [mark_source_span(replace(op, source=current_source), source_span_of(op)) for op in p.ast.reduces]
    p.ast.aggregates = [mark_source_span(replace(op, source=current_source), source_span_of(op)) for op in p.ast.aggregates]
    p.ast.shows = [
        mark_source_span(
            replace(show, target=Name(current_source))
            if isinstance(show.target, Name) and show.target.name == final_public_name else show,
            source_span_of(show),
        )
        for show in p.ast.shows
    ]
    p.ast.top_level_statements = [
        mark_source_span(
            replace(statement, target=Name(current_source))
            if isinstance(statement, ShowOp) and isinstance(statement.target, Name)
            and statement.target.name == final_public_name else statement,
            source_span_of(statement),
        )
        for statement in p.ast.top_level_statements
    ]
    p.show_exprs = [
        Name(current_source) if isinstance(expr, Name) and expr.name == final_public_name else expr
        for expr in (p.show_exprs or [])
    ]
    validate(p)

    map_op = p.ast.maps[0]
    map_position = operation_position(map_op)
    pre_filters = [op for op in p.ast.filters if operation_position(op) < map_position]
    post_filters = [op for op in p.ast.filters if operation_position(op) > map_position]
    tables = p.data_tables or {}
    if source not in tables:
        raise ValueError("native Record scalar bridge requires a concrete source table")
    rows = tables[source]
    if not rows:
        raise ValueError("native Record scalar bridge requires a non-empty source")

    def row_path(expr):
        if isinstance(expr, Name) and expr.name == "row":
            return ()
        if isinstance(expr, (Field, Property)):
            base = row_path(expr.base)
            if base is not None:
                return base + (expr.name,)
        return None

    def row_fields(expr):
        out=[]
        def walk(e):
            path=row_path(e)
            if path is not None and path:
                key=".".join(path)
                if key not in out: out.append(key)
                return
            if isinstance(e,(Binary,Compare,Logical)):
                walk(e.left)
                if getattr(e,"right",None) is not None: walk(e.right)
            elif isinstance(e,Conditional):
                walk(e.condition); walk(e.then_expr); walk(e.else_expr)
            elif isinstance(e,Call):
                for a in e.args: walk(a)
        walk(expr)
        return out

    needed=[]
    for op in pre_filters:
        for f in row_fields(op.predicate.expr):
            if f not in needed: needed.append(f)
    for f in row_fields(map_op.expr):
        if f not in needed: needed.append(f)
    if not needed:
        raise ValueError("native Record scalar bridge requires row fields")
    for f in needed:
        vals=[row.get(f) for row in rows]
        if not all(isinstance(v,(int,float)) and not isinstance(v,bool) for v in vals):
            raise ValueError(f"native Record scalar bridge supports numeric fields only: '{f}'")

    def terminal_show(name):
        return any(isinstance(sh.target,Name) and sh.target.name==name for sh in p.ast.shows)

    lines=["; ModuleID = 'slang-record-scalar-bridge'", 'source_filename = "slang"', '']
    if function_part:
        lines.extend(function_part); lines.append('')
    globals_=[]
    for f in needed:
        vals=[float(row[f]) for row in rows]
        g=f"data_{source}_{f}".replace('-','_')
        globals_.append((f,g,vals))
        elems=', '.join(f'double {v:.17e}' for v in vals)
        lines.append(f'@{g} = private constant [{len(vals)} x double] [{elems}]')
    lines += ['', 'declare i32 @printf(ptr, ...)', 'declare double @llvm.pow.f64(double, double)',
              '@fmt = private constant [7 x i8] c"%.17g\\0A\\00"',
              'define i32 @main() {', 'entry:']
    n=len(rows); cap=max(1,n)
    field_ptrs={}
    for f,g,vals in globals_:
        field_ptrs[f]=(g,len(vals))
    # One filtered buffer per required source field.
    fbuf={f:f'%fbuf_{i}' for i,f in enumerate(needed)}
    lines += [f'  %filtered_count = alloca i64']
    for f in needed:
        lines.append(f'  {fbuf[f]} = alloca [{cap} x double]')
    lines += ['  %scalar_count = alloca i64', f'  %scalar_buf = alloca [{cap} x double]',
              f'  %sort_buf = alloca [{cap} x double]', '  store i64 0, ptr %filtered_count',
              '  br label %filter_loop', 'filter_loop:',
              '  %fi = phi i64 [ 0, %entry ], [ %fnext, %filter_skip ]',
              f'  %fcond = icmp ult i64 %fi, {n}', '  br i1 %fcond, label %filter_body, label %filter_done',
              'filter_body:']
    field_values={}
    for f,g,_ in globals_:
        lines += [f'  %base_{f} = getelementptr inbounds [{n} x double], ptr @{g}, i64 0, i64 0',
                  f'  %ptr_{f} = getelementptr double, ptr %base_{f}, i64 %fi',
                  f'  %val_{f} = load double, ptr %ptr_{f}']
        field_values[f]=f'%val_{f}'
    predicate_values = [
        _llvm_collection_predicate(op.predicate.expr, lines, index + 1, signatures, field_values)
        for index, op in enumerate(pre_filters)
    ] or ['true']
    keep = predicate_values[0]
    for index, predicate_value in enumerate(predicate_values[1:], start=1):
        combined = f'%filter_predicate_and_{index}'
        lines.append(f'  {combined} = and i1 {keep}, {predicate_value}')
        keep = combined
    lines += [f'  br i1 {keep}, label %filter_keep, label %filter_skip', 'filter_keep:',
              '  %fc = load i64, ptr %filtered_count']
    for f in needed:
        lines += [f'  %fd_{f} = getelementptr [{cap} x double], ptr {fbuf[f]}, i64 0, i64 %fc',
                  f'  store double %val_{f}, ptr %fd_{f}']
    lines += ['  %fcn = add i64 %fc, 1', '  store i64 %fcn, ptr %filtered_count', '  br label %filter_skip',
              'filter_skip:', '  %fnext = add i64 %fi, 1', '  br label %filter_loop', 'filter_done:',
              '  store i64 0, ptr %scalar_count', '  br label %map_loop', 'map_loop:',
              '  %mi = phi i64 [ 0, %filter_done ], [ %mnext, %map_body ]',
              '  %mcount = load i64, ptr %filtered_count', '  %mcond = icmp ult i64 %mi, %mcount',
              '  br i1 %mcond, label %map_body, label %map_done', 'map_body:']
    map_fields={}
    for f in needed:
        lines += [f'  %mbase_{f} = getelementptr [{cap} x double], ptr {fbuf[f]}, i64 0, i64 0',
                  f'  %mptr_{f} = getelementptr double, ptr %mbase_{f}, i64 %mi',
                  f'  %mval_{f} = load double, ptr %mptr_{f}']
        map_fields[f]=f'%mval_{f}'
    mapped=_llvm_scalar_expr(map_op.expr,None,lines,2,signatures,map_fields)
    lines += ['  %mcount_now = load i64, ptr %scalar_count',
              f'  %mdst = getelementptr [{cap} x double], ptr %scalar_buf, i64 0, i64 %mcount_now',
              f'  store double {mapped}, ptr %mdst', '  %mcount_next = add i64 %mcount_now, 1',
              '  store i64 %mcount_next, ptr %scalar_count', '  %mnext = add i64 %mi, 1', '  br label %map_loop',
              'map_done:']
    if post_filters:
        lines += [f'  %post_filter_buf = alloca [{cap} x double]',
                  '  %post_filter_count = alloca i64', '  store i64 0, ptr %post_filter_count',
                  '  %post_filter_source_count = load i64, ptr %scalar_count',
                  '  br label %scalar_post_filter_loop', 'scalar_post_filter_loop:',
                  '  %spfi = phi i64 [ 0, %map_done ], [ %spfn, %scalar_post_filter_skip ]',
                  '  %spfc = icmp ult i64 %spfi, %post_filter_source_count',
                  '  br i1 %spfc, label %scalar_post_filter_body, label %scalar_post_filter_done',
                  'scalar_post_filter_body:',
                  f'  %spfp = getelementptr [{cap} x double], ptr %scalar_buf, i64 0, i64 %spfi',
                  '  %spfv = load double, ptr %spfp']
        post_values=[]
        for index, op in enumerate(post_filters, 1):
            pred_value=_llvm_collection_predicate(op.predicate.expr, lines, 100 + index, signatures, {'item':'%spfv','value':'%spfv'})
            post_values.append(pred_value)
        keep=post_values[0]
        for index, value in enumerate(post_values[1:], 1):
            combined=f'%scalar_post_filter_and_{index}'
            lines.append(f'  {combined} = and i1 {keep}, {value}')
            keep=combined
        lines += [f'  br i1 {keep}, label %scalar_post_filter_keep, label %scalar_post_filter_skip',
                  'scalar_post_filter_keep:',
                  '  %spfo = load i64, ptr %post_filter_count',
                  f'  %spfd = getelementptr [{cap} x double], ptr %post_filter_buf, i64 0, i64 %spfo',
                  '  store double %spfv, ptr %spfd', '  %spfon = add i64 %spfo, 1',
                  '  store i64 %spfon, ptr %post_filter_count',
                  '  br label %scalar_post_filter_skip',
                  'scalar_post_filter_skip:', '  %spfn = add i64 %spfi, 1',
                  '  br label %scalar_post_filter_loop', 'scalar_post_filter_done:',
                  '  %post_filtered_count = load i64, ptr %post_filter_count',
                  '  store i64 %post_filtered_count, ptr %scalar_count',
                  '  %sn = load i64, ptr %scalar_count',
                  '  br label %copy_loop']
    else:
        lines += ['  %sn = load i64, ptr %scalar_count', '  br label %copy_loop']
    copy_predecessor = 'scalar_post_filter_done' if post_filters else 'map_done'
    copy_source_buffer = '%post_filter_buf' if post_filters else '%scalar_buf'
    lines += ['copy_loop:',
              f'  %ci = phi i64 [ 0, %{copy_predecessor} ], [ %cnext, %copy_body ]',
              '  %ccond = icmp ult i64 %ci, %sn', '  br i1 %ccond, label %copy_body, label %sort_outer',
              'copy_body:', f'  %sptr = getelementptr [1 x double], ptr {copy_source_buffer}, i64 0, i64 %ci',
              f'  %sv = load double, ptr %sptr', f'  %sdst = getelementptr [{cap} x double], ptr %sort_buf, i64 0, i64 %ci',
              '  store double %sv, ptr %sdst', '  %cnext = add i64 %ci, 1', '  br label %copy_loop',
              'sort_outer:', '  br label %outer', 'outer:',
              '  %oi = phi i64 [ 0, %sort_outer ], [ %onext, %outer_advance ]',
              '  %olimit = sub i64 %sn, 1', '  %ocond = icmp ult i64 %oi, %olimit',
              '  br i1 %ocond, label %inner, label %sorted', 'inner:', '  br label %inner_loop', 'inner_loop:',
              '  %ji = phi i64 [ 0, %inner ], [ %jnext, %noswap ]', '  %jlimit = sub i64 %sn, 1',
              '  %jcond = icmp ult i64 %ji, %jlimit', '  br i1 %jcond, label %cmp_body, label %outer_advance',
              'cmp_body:', f'  %lp = getelementptr [{cap} x double], ptr %sort_buf, i64 0, i64 %ji',
              '  %rj = add i64 %ji, 1', f'  %rp = getelementptr [{cap} x double], ptr %sort_buf, i64 0, i64 %rj',
              '  %lv = load double, ptr %lp', '  %rv = load double, ptr %rp']
    cmp='ogt' if p.ast.sorts[0].spec.ascending else 'olt'
    lines += [f'  %swap = fcmp {cmp} double %lv, %rv', '  br i1 %swap, label %doswap, label %noswap',
              'doswap:', '  store double %rv, ptr %lp', '  store double %lv, ptr %rp', '  br label %noswap',
              'noswap:', '  %jnext = add i64 %ji, 1', '  br label %inner_loop',
              'outer_advance:', '  %onext = add i64 %oi, 1', '  br label %outer', 'sorted:']
    if p.ast.reduces:
        red=p.ast.reduces[0]
        if not isinstance(red.initial, Literal) or not isinstance(red.initial.value, (int,float)) or isinstance(red.initial.value, bool):
            raise ValueError("native Record scalar bridge requires a numeric reduce initial value")
        expr=red.expr
        if not (isinstance(expr, Binary) and isinstance(expr.left, Name) and expr.left.name == "acc" and isinstance(expr.right, Name) and expr.right.name == "item" and expr.op in {"+","-","*","/"}):
            raise ValueError("native Record scalar bridge supports reduce expressions of the form 'acc <op> item'")
        init=float(red.initial.value)
        lines += [f'  %reduce_acc = alloca double', f'  store double {init:.17e}, ptr %reduce_acc',
                  '  br label %reduce_loop', 'reduce_loop:',
                  '  %reduce_i = phi i64 [ 0, %sorted ], [ %reduce_next, %reduce_body ]',
                  '  %reduce_cond = icmp ult i64 %reduce_i, %sn',
                  '  br i1 %reduce_cond, label %reduce_body, label %reduce_done',
                  'reduce_body:',
                  f'  %reduce_ptr = getelementptr [{cap} x double], ptr %sort_buf, i64 0, i64 %reduce_i',
                  '  %reduce_item = load double, ptr %reduce_ptr',
                  '  %reduce_old = load double, ptr %reduce_acc']
        opmap={"+":"fadd","-":"fsub","*":"fmul","/":"fdiv"}
        lines.append(f'  %reduce_new = {opmap[expr.op]} double %reduce_old, %reduce_item')
        lines += ['  store double %reduce_new, ptr %reduce_acc', '  %reduce_next = add i64 %reduce_i, 1', '  br label %reduce_loop',
                  'reduce_done:', '  %reduce_result = load double, ptr %reduce_acc']
        if terminal_show(red.result):
            lines.append('  call i32 (ptr, ...) @printf(ptr @fmt, double %reduce_result)')
    elif p.ast.aggregates:
        agg=p.ast.aggregates[0]
        lines += ['  %acc = alloca double', '  store double 0.00000000000000000e+00, ptr %acc',
                  '  br label %agg_loop', 'agg_loop:', '  %ai = phi i64 [ 0, %sorted ], [ %anext, %agg_body ]',
                  '  %acond = icmp ult i64 %ai, %sn', '  br i1 %acond, label %agg_body, label %agg_done', 'agg_body:',
                  f'  %ap = getelementptr [{cap} x double], ptr %sort_buf, i64 0, i64 %ai',
                  '  %av = load double, ptr %ap', '  %ac = load double, ptr %acc', '  %an = fadd double %ac, %av',
                  '  store double %an, ptr %acc', '  %anext = add i64 %ai, 1', '  br label %agg_loop',
                  'agg_done:', '  %result = load double, ptr %acc']
        if agg.operation in {'average','avg'}:
            lines += ['  %scf = uitofp i64 %sn to double', '  %result_avg = fdiv double %result, %scf']
            result='%result_avg'
        else:
            result='%result'
        if terminal_show(agg.result):
            lines.append(f'  call i32 (ptr, ...) @printf(ptr @fmt, double {result})')
    else:
        lines += ['  br label %show_loop', 'show_loop:', '  %si = phi i64 [ 0, %sorted ], [ %snext, %show_body ]',
                  '  %scond = icmp ult i64 %si, %sn', '  br i1 %scond, label %show_body, label %finish',
                  'show_body:', f'  %showp = getelementptr [{cap} x double], ptr %sort_buf, i64 0, i64 %si',
                  '  %showv = load double, ptr %showp', '  call i32 (ptr, ...) @printf(ptr @fmt, double %showv)',
                  '  %snext = add i64 %si, 1', '  br label %show_loop', 'finish:']
    lines += ['  ret i32 0', '}']
    return '\n'.join(lines)



def _record_filter_scalar_text_sort_llvm_ir(p: Program, function_part=None, signatures=None):
    """Lower Record -> filter -> Text scalar projection -> sort.

    The scalar boundary stores Text pointers.  Filter predicates may mix Text
    and Number comparisons; Text comparisons use strcmp and numeric portions
    reuse the normal f64 predicate lowering.
    """
    validate(p)
    signatures = signatures or {}
    if len(p.ast.sorts) != 1 or len(p.ast.maps) != 1:
        raise ValueError("native Record text scalar bridge requires one map and one sort")
    if p.ast.reduces:
        if len(p.ast.reduces) != 1:
            raise ValueError("native Record text scalar bridge supports exactly one reduce terminal")
        red = p.ast.reduces[0]
        if not isinstance(red.initial, Literal) or not isinstance(red.initial.value, str):
            raise ValueError("native Text reduce requires a Text literal initial accumulator")
        if not (isinstance(red.expr, Binary) and isinstance(red.expr.left, Name) and red.expr.left.name == "acc"
                and isinstance(red.expr.right, Name) and red.expr.right.name == "item" and red.expr.op == "+"):
            raise ValueError("native Text reduce supports only 'acc + item'")
    if p.ast.aggregates:
        if len(p.ast.aggregates) != 1 or p.ast.aggregates[0].operation not in {"count", "min", "max"}:
            raise ValueError("native Record text scalar bridge supports only count, min, or max")
    source = p.ast.filters[0].source if p.ast.filters else p.ast.maps[0].source
    rows = (p.data_tables or {}).get(source)
    if not rows:
        raise ValueError("native Record text scalar bridge requires a non-empty source")

    def row_path(expr):
        if isinstance(expr, Name) and expr.name == "row":
            return ()
        if isinstance(expr, (Field, Property)):
            base = row_path(expr.base)
            if base is not None:
                return base + (expr.name,)
        return None

    path = row_path(p.ast.maps[0].expr)
    if not path:
        raise ValueError("native Record text scalar bridge currently requires a direct row field projection")
    field = ".".join(path)
    values = [row.get(field) for row in rows]
    if not all(isinstance(v, str) for v in values):
        raise ValueError(f"native Record text scalar bridge requires a Text field: '{field}'")

    def collect_paths(expr):
        found=[]
        def walk(e):
            rp=row_path(e)
            if rp is not None and rp:
                found.append(".".join(rp)); return
            if isinstance(e,(Binary,Compare,Logical)):
                walk(e.left)
                if getattr(e,"right",None) is not None: walk(e.right)
            elif isinstance(e,Conditional):
                walk(e.condition); walk(e.then_expr); walk(e.else_expr)
            elif isinstance(e,Call):
                for arg in e.args: walk(arg)
        walk(expr)
        return found

    filter_fields=[]
    for op in p.ast.filters:
        for f in collect_paths(op.predicate.expr):
            if f not in filter_fields: filter_fields.append(f)
    filter_types={}
    for f in filter_fields:
        fvals=[row.get(f) for row in rows]
        if not fvals or not all(isinstance(v,str) for v in fvals) and not all(isinstance(v,(int,float)) and not isinstance(v,bool) for v in fvals):
            raise ValueError(f"native Record text scalar bridge supports Number/Text filter fields only: '{f}'")
        filter_types[f] = "text" if all(isinstance(v,str) for v in fvals) else "number"

    predicate_literals=[]
    def collect_literals(expr):
        if isinstance(expr, Literal) and isinstance(expr.value,str):
            if expr.value not in predicate_literals: predicate_literals.append(expr.value)
        elif isinstance(expr,(Binary,Compare,Logical)):
            collect_literals(expr.left)
            if getattr(expr,"right",None) is not None: collect_literals(expr.right)
        elif isinstance(expr,Conditional):
            collect_literals(expr.condition); collect_literals(expr.then_expr); collect_literals(expr.else_expr)
        elif isinstance(expr,Call):
            for arg in expr.args: collect_literals(arg)
    for op in p.ast.filters: collect_literals(op.predicate.expr)

    lines=["; ModuleID = 'slang-record-text-scalar-bridge'", 'source_filename = "slang"', '']
    if function_part:
        lines.extend(function_part); lines.append('')

    # Projection values are kept as individual immutable globals.
    ptr_globals=[]
    for i,v in enumerate(values):
        g=f"text_{i}"
        enc, text_len = _llvm_c_string(v)
        lines.append(f'@{g} = private constant [{text_len} x i8] c"{enc}"')
        ptr_globals.append(g)

    # Predicate Text literals and row Text fields use pointer arrays.
    pred_literal_globals={}
    for i,v in enumerate(predicate_literals):
        g=f"predicate_text_{i}"
        enc,ln=_llvm_c_string(v)
        lines.append(f'@{g} = private constant [{ln} x i8] c"{enc}"')
        pred_literal_globals[v]=(g,ln)

    filter_globals={}
    for fi,f in enumerate(filter_fields):
        fvals=[row.get(f) for row in rows]
        safe=f.replace('.','_')
        if filter_types[f] == "text":
            names=[]
            for ri,v in enumerate(fvals):
                g=f"filter_text_{fi}_{ri}"
                enc,ln=_llvm_c_string(v)
                lines.append(f'@{g} = private constant [{ln} x i8] c"{enc}"')
                names.append(g)
            arr=f"filter_text_ptrs_{fi}"
            elems=', '.join(f'ptr @{g}' for g in names)
            lines.append(f'@{arr} = private constant [{len(names)} x ptr] [{elems}]')
            filter_globals[f]=(filter_types[f],arr,len(names))
        else:
            arr=f"filter_num_{fi}"
            elems=', '.join(f'double {float(v):.17e}' for v in fvals)
            lines.append(f'@{arr} = private constant [{len(fvals)} x double] [{elems}]')
            filter_globals[f]=(filter_types[f],arr,len(fvals))

    n=len(values); cap=max(1,n)
    if p.ast.reduces:
        initial = p.ast.reduces[0].initial.value
        enc, reduce_initial_len = _llvm_c_string(initial)
        lines.append(f'@reduce_initial = private constant [{reduce_initial_len} x i8] c\"{enc}\"')
    lines += [
        '', 'declare i32 @printf(ptr, ...)', 'declare i32 @strcmp(ptr, ptr)', 'declare i64 @strlen(ptr)', 'declare ptr @malloc(i64)', 'declare ptr @memcpy(ptr, ptr, i64)',
        '@fmt_text = private constant [4 x i8] c"%s\\0A\\00"',
        '@fmt_num_i64 = private constant [5 x i8] c"%ld\\0A\\00"',
        '@fmt_text_error = private constant [49 x i8] c"aggregate cannot operate on an empty collection\\0A\\00"',
        'define i32 @main() {', 'entry:',
        f'  %sort_buf = alloca [{cap} x ptr]',
        '  %scalar_count = alloca i64',
        '  store i64 0, ptr %scalar_count',
        '  br label %map_loop',
        'map_loop:',
        '  %mi = phi i64 [ 0, %entry ], [ %mnext, %map_advance ]',
        f'  %mcond = icmp ult i64 %mi, {n}',
        '  br i1 %mcond, label %map_body, label %map_done',
        'map_body:'
    ]

    # Load typed predicate operands for the current source row.
    typed_values={}
    for f in filter_fields:
        kind,g,gn=filter_globals[f]
        safe=f.replace('.','_')
        if kind == 'text':
            names=[]
            for ri,row in enumerate(rows):
                gname=f"filter_text_{filter_fields.index(f)}_{ri}"
                ln=_llvm_c_string(row.get(f))[1]
                name=f'%fsel_{safe}_{ri}'
                lines.append(f'  {name} = getelementptr inbounds [{ln} x i8], ptr @{gname}, i64 0, i64 0')
                names.append(name)
            current=names[0]
            for ri in range(1,len(names)):
                eq=f'%fidx_{safe}_{ri}'
                sel=f'%fselect_{safe}_{ri}'
                lines.append(f'  {eq} = icmp eq i64 %mi, {ri}')
                lines.append(f'  {sel} = select i1 {eq}, ptr {names[ri]}, ptr {current}')
                current=sel
            typed_values[f]=('text',current)
        else:
            lines += [
                f'  %fbase_{safe} = getelementptr inbounds [{gn} x double], ptr @{g}, i64 0, i64 0',
                f'  %fptr_{safe} = getelementptr double, ptr %fbase_{safe}, i64 %mi',
                f'  %fval_{safe} = load double, ptr %fptr_{safe}',
            ]
            typed_values[f]=('number',f'%fval_{safe}')

    def text_operand(expr):
        rp=row_path(expr)
        if rp is not None and rp:
            key='.'.join(rp)
            tv=typed_values.get(key)
            if tv and tv[0]=='text': return tv[1]
            raise ValueError(f"native Record text predicate field '{key}' is not Text")
        if isinstance(expr,Literal) and isinstance(expr.value,str):
            g,ln=pred_literal_globals[expr.value]
            name=f'%textlit_{len(lines)}'
            lines.append(f'  {name} = getelementptr inbounds [{ln} x i8], ptr @{g}, i64 0, i64 0')
            return name
        raise ValueError('native Record Text predicate requires a Text row field or Text literal')

    def mixed_pred(expr,serial=1):
        if isinstance(expr,Literal) and isinstance(expr.value,bool): return 'true' if expr.value else 'false'
        if isinstance(expr,Logical):
            if expr.op=='not':
                v=mixed_pred(expr.left,serial); name=f'%t_not_{len(lines)}'; lines.append(f'  {name} = xor i1 {v}, true'); return name
            if expr.op in {'and','or'}:
                a=mixed_pred(expr.left,serial); b=mixed_pred(expr.right,serial); name=f'%t_logic_{len(lines)}'; lines.append(f'  {name} = {expr.op} i1 {a}, {b}'); return name
        if isinstance(expr,Compare) and expr.op in {'>','>=','<','<=','==','!='}:
            paths=collect_paths(expr.left)+collect_paths(expr.right)
            is_text=any(typed_values.get(k,('',None))[0]=='text' for k in paths)
            if is_text:
                lv=text_operand(expr.left); rv=text_operand(expr.right)
                c=f'%strcmp_{len(lines)}'; lines.append(f'  {c} = call i32 @strcmp(ptr {lv}, ptr {rv})')
                pred={'>':'sgt','>=':'sge','<':'slt','<=':'sle','==':'eq','!=':'ne'}[expr.op]
                out=f'%t_cmp_{len(lines)}'; lines.append(f'  {out} = icmp {pred} i32 {c}, 0'); return out
            numeric={k:v for k,(kind,v) in typed_values.items() if kind=='number'}
            return _llvm_collection_predicate(expr,lines,serial,signatures,numeric)
        raise ValueError('native Record text scalar bridge supports Text/Number comparisons and logical predicates')

    if p.ast.filters:
        predicate_values = [mixed_pred(op.predicate.expr, index + 1) for index, op in enumerate(p.ast.filters)]
        keep = predicate_values[0]
        for index, predicate_value in enumerate(predicate_values[1:], start=1):
            combined = f'%text_filter_and_{index}'
            lines.append(f'  {combined} = and i1 {keep}, {predicate_value}')
            keep = combined
        lines += [f'  br i1 {keep}, label %map_keep, label %map_skip', 'map_keep:']

    # Select the projected string corresponding to the source row index.
    for i,gg in enumerate(ptr_globals):
        base=f'  %p_{i} = getelementptr inbounds [{len(values[i].encode("utf-8"))+1} x i8], ptr @{gg}, i64 0, i64 0'
        lines.append(base)
    lines.append('  %dst_i = load i64, ptr %scalar_count')
    _, text_len_0 = _llvm_c_string(values[0])
    lines.append(f'  %p_sel0 = getelementptr inbounds [{text_len_0} x i8], ptr @{ptr_globals[0]}, i64 0, i64 0')
    current='%p_sel0'
    for i in range(1,n):
        lines.append(f'  %idxeq{i} = icmp eq i64 %mi, {i}')
        lines.append(f'  %p_sel{i} = select i1 %idxeq{i}, ptr %p_{i}, ptr {current}')
        current=f'%p_sel{i}'
    lines += [
        f'  %sdst = getelementptr [{cap} x ptr], ptr %sort_buf, i64 0, i64 %dst_i',
        f'  store ptr {current}, ptr %sdst',
        '  %mnext_keep_dummy = add i64 %mi, 1',
        '  %next_count = add i64 %dst_i, 1',
        '  store i64 %next_count, ptr %scalar_count',
        '  br label %map_advance',
        'map_skip:',
        '  br label %map_advance',
        'map_advance:',
        '  %mnext = add i64 %mi, 1',
        '  br label %map_loop',
        'map_done:',
        '  %sn = load i64, ptr %scalar_count',
        '  %has_values = icmp ne i64 %sn, 0',
        '  br i1 %has_values, label %outer, label %sorted',
        'outer:',
        '  %oi = phi i64 [ 0, %map_done ], [ %onext, %outer_advance ]',
        '  %olimit = sub i64 %sn, 1',
        '  %ocond = icmp ult i64 %oi, %olimit',
        '  br i1 %ocond, label %inner, label %sorted',
        'inner:', '  br label %inner_loop',
        'inner_loop:',
        '  %ji = phi i64 [ 0, %inner ], [ %jnext, %noswap ]',
        '  %jlimit = sub i64 %sn, 1',
        '  %jcond = icmp ult i64 %ji, %jlimit',
        '  br i1 %jcond, label %cmp_body, label %outer_advance',
        'cmp_body:',
        f'  %lp = getelementptr [{cap} x ptr], ptr %sort_buf, i64 0, i64 %ji',
        '  %rj = add i64 %ji, 1',
        f'  %rp = getelementptr [{cap} x ptr], ptr %sort_buf, i64 0, i64 %rj',
        '  %lv = load ptr, ptr %lp', '  %rv = load ptr, ptr %rp',
        '  %cmp = call i32 @strcmp(ptr %lv, ptr %rv)',
    ]
    pred='sgt' if p.ast.sorts[0].spec.ascending else 'slt'
    lines += [
        f'  %swap = icmp {pred} i32 %cmp, 0',
        '  br i1 %swap, label %doswap, label %noswap',
        'doswap:', '  store ptr %rv, ptr %lp', '  store ptr %lv, ptr %rp', '  br label %noswap',
        'noswap:', '  %jnext = add i64 %ji, 1', '  br label %inner_loop',
        'outer_advance:', '  %onext = add i64 %oi, 1', '  br label %outer',
        'sorted:'
    ]
    # Unified Text terminal contract: all supported terminal operations consume
    # the same sorted scalar buffer and differ only in their terminal strategy.
    terminal_kind, _terminal_op = _native_terminal_contract(p)
    if terminal_kind is not None:
        if terminal_kind == 'reduce':
            lines += [
                '  %reduce_acc = alloca ptr',
                f'  %reduce_init = getelementptr inbounds [{reduce_initial_len} x i8], ptr @reduce_initial, i64 0, i64 0',
                '  store ptr %reduce_init, ptr %reduce_acc',
                '  br label %text_terminal_loop',
                'text_terminal_loop:',
                '  %text_terminal_i = phi i64 [ 0, %sorted ], [ %reduce_next, %text_terminal_reduce_copy ]',
                '  %text_terminal_cond = icmp ult i64 %text_terminal_i, %sn',
                '  br i1 %text_terminal_cond, label %text_terminal_body, label %text_terminal_done',
                'text_terminal_body:',
                f'  %reduce_ptr = getelementptr [{cap} x ptr], ptr %sort_buf, i64 0, i64 %text_terminal_i',
                '  %reduce_item = load ptr, ptr %reduce_ptr',
                '  %reduce_old = load ptr, ptr %reduce_acc',
                '  %reduce_len_a = call i64 @strlen(ptr %reduce_old)',
                '  %reduce_len_b = call i64 @strlen(ptr %reduce_item)',
                '  %reduce_total = add i64 %reduce_len_a, %reduce_len_b',
                '  %reduce_alloc = add i64 %reduce_total, 1',
                '  %reduce_new = call ptr @malloc(i64 %reduce_alloc)',
                '  %reduce_ok = icmp ne ptr %reduce_new, null',
                '  br i1 %reduce_ok, label %text_terminal_reduce_copy, label %text_terminal_done',
                'text_terminal_reduce_copy:',
                '  call ptr @memcpy(ptr %reduce_new, ptr %reduce_old, i64 %reduce_len_a)',
                '  %reduce_tail = getelementptr i8, ptr %reduce_new, i64 %reduce_len_a',
                '  call ptr @memcpy(ptr %reduce_tail, ptr %reduce_item, i64 %reduce_len_b)',
                '  %reduce_end = getelementptr i8, ptr %reduce_new, i64 %reduce_total',
                '  store i8 0, ptr %reduce_end',
                '  store ptr %reduce_new, ptr %reduce_acc',
                '  %reduce_next = add i64 %text_terminal_i, 1',
                '  br label %text_terminal_loop',
                'text_terminal_done:',
                '  %reduce_result = load ptr, ptr %reduce_acc',
                '  call i32 (ptr, ...) @printf(ptr @fmt_text, ptr %reduce_result)',
                '  br label %finish'
            ]
        elif terminal_kind == 'count':
            lines += [
                '  call i32 (ptr, ...) @printf(ptr @fmt_num_i64, i64 %sn)',
                '  br label %finish'
            ]
        elif terminal_kind in {'min', 'max'}:
            lines += [
                '  %text_terminal_nonempty = icmp ne i64 %sn, 0',
                '  br i1 %text_terminal_nonempty, label %text_terminal_value, label %text_terminal_empty',
                'text_terminal_empty:',
                '  call i32 (ptr, ...) @printf(ptr @fmt_text_error)',
                '  br label %finish_error',
                'text_terminal_value:',
                f'  %text_terminal_last = sub i64 %sn, 1',
            ]
            ascending = p.ast.sorts[0].spec.ascending
            idx = ('0' if terminal_kind == 'min' else '%text_terminal_last') if ascending else ('%text_terminal_last' if terminal_kind == 'min' else '0')
            lines += [
                f'  %text_terminal_ptr = getelementptr [{cap} x ptr], ptr %sort_buf, i64 0, i64 {idx}',
                '  %text_terminal_result = load ptr, ptr %text_terminal_ptr',
                '  call i32 (ptr, ...) @printf(ptr @fmt_text, ptr %text_terminal_result)',
                '  br label %finish'
            ]
        else:
            raise ValueError(f"native Record text scalar bridge does not support terminal '{terminal_kind}'")
    else:
        lines += [
            '  br label %show_loop',
            'show_loop:', '  %si = phi i64 [ 0, %sorted ], [ %snext, %show_body ]',
            '  %scond = icmp ult i64 %si, %sn', '  br i1 %scond, label %show_body, label %finish',
            'show_body:', f'  %showp = getelementptr [{cap} x ptr], ptr %sort_buf, i64 0, i64 %si',
            '  %showv = load ptr, ptr %showp', '  call i32 (ptr, ...) @printf(ptr @fmt_text, ptr %showv)',
            '  %snext = add i64 %si, 1', '  br label %show_loop'
        ]
    lines += ['finish_error:', '  ret i32 1', 'finish:', '  ret i32 0', '}']
    return '\n'.join(lines)


def sort_llvm_ir(p:Program, function_part=None, signatures=None, schema_contract=None):
    """Lower a numeric collection pipeline ending in a stable sort.

    The native subset stores one numeric value per row.  A terminal sort is
    therefore lowered as a deterministic stable in-place bubble sort.  The
    algorithm is deliberately simple and explicit; backend optimization can
    replace it later without changing S-Lang semantics.
    """
    validate(p)
    if p.bodies or p.simulation or p.ast.reduces or p.ast.aggregates:
        raise ValueError("native sort backend currently accepts data/filter/map/sort programs")
    if signatures is None:
        signatures = {}
    if len(p.ast.sorts) != 1:
        raise ValueError("native sort backend currently requires exactly one sort operation")
    sort=p.ast.sorts[0]
    tables=p.data_tables or {}
    # 1.10.38: build the backend field-storage table from the semantic schema
    # contract once.  Lowering resolves row.<field> through this table rather
    # than rediscovering field types from AST record declarations.
    schema_by_binding={}
    for binding, in_schema, out_schema in (schema_contract or getattr(p, "_backend_schema_contract", ())):
        schema_by_binding[binding]=(in_schema, out_schema)
    def schema_fields(binding):
        pair=schema_by_binding.get(binding)
        if pair is None:
            matches=[v for k,v in schema_by_binding.items() if k.split("#",1)[0]==binding]
            if len(matches)==1: pair=matches[0]
        schema=pair[1] if pair else None
        if schema is None: return None
        return {f.name:f.type_name for f in getattr(schema,"fields",())}
    ordered=[]; available=set(tables); remaining=list(p.ast.filters)+list(p.ast.maps)
    while remaining:
        progress=False
        for op in remaining[:]:
            if op.source in available:
                ordered.append(op); available.add(op.result); remaining.remove(op); progress=True
        if not progress:
            raise ValueError("native sort backend requires a forward acyclic pipeline")
    if sort.source not in available:
        raise ValueError(f"unknown sort source '{sort.source}'")

    def field_for(expr):
        out=[]
        def walk(e):
            if isinstance(e,(Field,Property)) and isinstance(e.base,Name) and e.base.name=='row': out.append(e.name)
            elif isinstance(e,(Binary,Compare,Logical)):
                walk(e.left)
                if getattr(e,'right',None) is not None: walk(e.right)
            elif isinstance(e,Call):
                for a in e.args: walk(a)
        walk(expr)
        return out[0] if len(set(out))==1 else None

    globals_=[]; source_info={}
    source_fields={}
    all_ops=ordered+[sort]
    for op in all_ops:
        expr=(op.predicate.expr if isinstance(op,FilterOp) else op.expr if isinstance(op,MapOp) else op.spec.expr)
        field=field_for(expr)
        if field is not None:
            source_fields.setdefault(op.source, field)
        if op.source not in tables or op.source in source_info: continue
        if field is None:
            field=source_fields.get(op.source)
        if field is None: raise ValueError("native sort backend requires one numeric row field per operation")
        vals=[]
        for row in tables[op.source]:
            v=row.get(field)
            if not isinstance(v,(int,float)): raise ValueError(f"native collection field '{field}' in '{op.source}' must be numeric")
            vals.append(float(v))
        gname=f"data_{op.source}_{field}".replace('-','_')
        globals_.append((gname,vals)); source_info[op.source]=(gname,len(vals))

    lines=["; ModuleID = 'slang-sort'", 'source_filename = "slang"', '']
    if function_part:
        lines.extend(function_part); lines.append('')
    for gname,vals in globals_:
        elems=', '.join(f'double {v:.17e}' for v in vals) or 'double 0.0'
        lines.append(f'@{gname} = private constant [{len(vals) if vals else 1} x double] [{elems}]')
    lines += ['', 'declare i32 @printf(ptr, ...)', 'declare double @llvm.pow.f64(double, double)', '@fmt = private constant [7 x i8] c"%.17g\\0A\\00"', '', 'define i32 @main() {', 'entry:']

    alloc={}
    for i,op in enumerate(ordered,1):
        cap=(source_info[op.source][1] if op.source in source_info else alloc[op.source][2]) or 1
        alloc[op.result]=(f'%buf{i}',f'%count{i}',cap)
        lines += [f'  %buf{i} = alloca [{cap} x double]', f'  %count{i} = alloca i64']
    sort_cap=(source_info[sort.source][1] if sort.source in source_info else alloc[sort.source][2]) or 1
    si=len(ordered)+1
    sortbuf=f'%buf{si}'; sortcount=f'%count{si}'
    lines += [f'  {sortbuf} = alloca [{sort_cap} x double]', f'  {sortcount} = alloca i64']

    desc={}
    for source,(gname,n) in source_info.items():
        ptr=f'getelementptr inbounds [{n if n else 1} x double], ptr @{gname}, i64 0, i64 0'
        desc[source]=(ptr,str(n),n)
    for i,op in enumerate(ordered,1):
        buf,count,cap=alloc[op.result]
        desc[op.result]=(f'getelementptr [{cap} x double], ptr {buf}, i64 0, i64 0',count,cap)

    current='entry'
    if ordered: lines.append('  br label %entry0'); current='entry0'; lines.append('entry0:')
    for i,op in enumerate(ordered,1):
        buf,count,cap=alloc[op.result]; srcptr,srccount,src_cap=desc[op.source]
        loop=f'loop{i}'; body=f'body{i}'; done=f'done{i}'; skip=f'skip{i}'
        lines += [f'  store i64 0, ptr {count}', f'  br label %{loop}', f'{loop}:',
                  f'  %i{i} = phi i64 [ 0, %{current} ], [ %next{i}, %{skip} ]',
                  f'  %src_count{i} = add i64 0, {srccount}' if srccount.isdigit() else f'  %src_count{i} = load i64, ptr {srccount}',
                  f'  %cond{i} = icmp ult i64 %i{i}, %src_count{i}', f'  br i1 %cond{i}, label %{body}, label %{done}', f'{body}:',
                  f'  %base{i} = {srcptr}', f'  %srcptr{i} = getelementptr double, ptr %base{i}, i64 %i{i}', f'  %value{i} = load double, ptr %srcptr{i}']
        stage_field = source_fields.get(op.source)
        field_values = {stage_field: f"%value{i}"} if stage_field else {}
        if isinstance(op,FilterOp):
            keep=_llvm_collection_predicate(op.predicate.expr,lines,i,signatures,field_values)
            lines += [f'  br i1 {keep}, label %keepblock{i}, label %{skip}', f'keepblock{i}:',
                      f'  %oc{i} = load i64, ptr {count}', f'  %dst{i} = getelementptr [{cap} x double], ptr {buf}, i64 0, i64 %oc{i}',
                      f'  store double %value{i}, ptr %dst{i}', f'  %on{i} = add i64 %oc{i}, 1', f'  store i64 %on{i}, ptr {count}', f'  br label %{skip}']
        else:
            expr=_llvm_scalar_expr(op.expr,srcptr,lines,i,signatures,field_values)
            lines += [f'  %dst{i} = getelementptr [{cap} x double], ptr {buf}, i64 0, i64 %i{i}', f'  store double {expr}, ptr %dst{i}', f'  br label %{skip}']
        lines += [f'{skip}:', f'  %next{i} = add i64 %i{i}, 1', f'  br label %{loop}', f'{done}:']
        if isinstance(op,MapOp):
            if srccount.isdigit(): lines.append(f'  store i64 {srccount}, ptr {count}')
            else:
                lines.append(f'  %map_source_count{i} = load i64, ptr {srccount}'); lines.append(f'  store i64 %map_source_count{i}, ptr {count}')
        current=done

    srcptr,srccount,src_cap=desc[sort.source]
    lines += [f'  store i64 0, ptr {sortcount}', f'  br label %copy_loop', 'copy_loop:',
              f'  %copy_i = phi i64 [ 0, %{current} ], [ %copy_next, %copy_body ]',
              f'  %copy_src_count = add i64 0, {srccount}' if srccount.isdigit() else f'  %copy_src_count = load i64, ptr {srccount}',
              '  %copy_cond = icmp ult i64 %copy_i, %copy_src_count', '  br i1 %copy_cond, label %copy_body, label %sort_outer_init',
              'copy_body:', f'  %copy_base = {srcptr}', '  %copy_src = getelementptr double, ptr %copy_base, i64 %copy_i',
              '  %copy_v = load double, ptr %copy_src', f'  %copy_dst = getelementptr [{sort_cap} x double], ptr {sortbuf}, i64 0, i64 %copy_i',
              '  store double %copy_v, ptr %copy_dst', '  %copy_next = add i64 %copy_i, 1', '  br label %copy_loop',
              'sort_outer_init:', f'  store i64 {0}, ptr {sortcount}',
              '  br label %outer', 'outer:', '  %outer_i = phi i64 [ 0, %sort_outer_init ], [ %outer_next, %outer_advance ]',
              f'  %n = add i64 0, {srccount}' if srccount.isdigit() else f'  %n = load i64, ptr {srccount}',
              '  %outer_limit = sub i64 %n, 1', '  %outer_cond = icmp ult i64 %outer_i, %outer_limit',
              '  br i1 %outer_cond, label %inner_init, label %sort_done',
              'inner_init:', '  br label %inner', 'inner:',
              '  %inner_j = phi i64 [ 0, %inner_init ], [ %inner_next, %no_swap ]',
              '  %inner_limit = sub i64 %n, 1', '  %inner_cond = icmp ult i64 %inner_j, %inner_limit',
              '  br i1 %inner_cond, label %inner_body, label %outer_advance', 'inner_body:',
              f'  %left_ptr = getelementptr [{sort_cap} x double], ptr {sortbuf}, i64 0, i64 %inner_j',
              '  %right_j = add i64 %inner_j, 1', f'  %right_ptr = getelementptr [{sort_cap} x double], ptr {sortbuf}, i64 0, i64 %right_j',
              '  %left = load double, ptr %left_ptr', '  %right = load double, ptr %right_ptr']
    cmp='ogt' if sort.spec.ascending else 'olt'
    lines += [f'  %swap = fcmp {cmp} double %left, %right', '  br i1 %swap, label %do_swap, label %no_swap',
              'do_swap:', '  store double %right, ptr %left_ptr', '  store double %left, ptr %right_ptr', '  br label %no_swap',
              'no_swap:', '  %inner_next = add i64 %inner_j, 1', '  br label %inner',
              'outer_advance:', '  %outer_next = add i64 %outer_i, 1', '  br label %outer', 'sort_done:']
    # Record actual source count after copy; this is used for printing.
    if srccount.isdigit(): lines.append(f'  store i64 {srccount}, ptr {sortcount}')
    else: lines.append(f'  %final_src_count = load i64, ptr {srccount}'); lines.append(f'  store i64 %final_src_count, ptr {sortcount}')
    lines += ['  br label %show_loop', 'show_loop:', '  %show_i = phi i64 [ 0, %sort_done ], [ %show_next, %show_body ]',
              f'  %show_n = load i64, ptr {sortcount}', '  %show_cond = icmp ult i64 %show_i, %show_n',
              '  br i1 %show_cond, label %show_body, label %finish', 'show_body:',
              f'  %show_ptr = getelementptr [{sort_cap} x double], ptr {sortbuf}, i64 0, i64 %show_i',
              '  %show_v = load double, ptr %show_ptr', '  call i32 (ptr, ...) @printf(ptr @fmt, double %show_v)',
              '  %show_next = add i64 %show_i, 1', '  br label %show_loop', 'finish:', '  ret i32 0', '}']
    return '\n'.join(lines)


def _native_terminal_contract(p: Program):
    """Select one terminal operation shared by native scalar backends."""
    reduces = list(p.ast.reduces); aggregates = list(p.ast.aggregates)
    if reduces and aggregates: raise ValueError("native terminal contract cannot combine reduce and aggregate")
    if len(reduces) > 1 or len(aggregates) > 1: raise ValueError("native terminal contract requires exactly one terminal operation")
    if reduces: return ("reduce", reduces[0])
    if aggregates: return (aggregates[0].operation, aggregates[0])
    return (None, None)


def _record_preserving_pipeline_aggregate_llvm_ir(p: Program, function_part=None, signatures=None):
    """Lower data-table filter -> sort -> scalar map -> aggregate pipelines.

    Unlike the scalar collection backend, this representation keeps every
    numeric field required by the pipeline in parallel buffers until the
    pipeline crosses an explicit scalar ``map`` boundary.  This preserves
    ``row.<field>`` semantics through filtering and sorting.
    """
    validate(p)
    if p.bodies or p.simulation or len(p.ast.sorts) != 1 or len(p.ast.aggregates) != 1:
        raise ValueError("native record-preserving pipeline requires one sort and one aggregate")
    if len(p.ast.reduces) != 0 or len(p.ast.maps) != 1 or len(p.ast.filters) != 1:
        raise ValueError("native record-preserving pipeline supports filter -> sort -> map -> aggregate")
    filt, sort, mp, agg = p.ast.filters[0], p.ast.sorts[0], p.ast.maps[0], p.ast.aggregates[0]
    if filt.result != sort.source or sort.result != mp.source or mp.result != agg.source:
        raise ValueError("native record-preserving pipeline requires filter -> sort -> map -> aggregate order")
    if agg.operation not in {"sum", "average", "avg", "min", "max"}:
        raise ValueError("native record-preserving pipeline currently supports numeric sum/average/min/max")
    tables = p.data_tables or {}
    rows = tables.get(filt.source)
    if rows is None:
        raise ValueError(f"unknown data source '{filt.source}'")
    if not rows:
        raise ValueError("native record-preserving pipeline requires a non-empty data source")

    def fields(expr):
        out=[]
        def walk(e):
            if isinstance(e,(Field,Property)) and isinstance(e.base,Name) and e.base.name == 'row':
                if e.name not in out: out.append(e.name)
            elif isinstance(e,(Binary,Compare,Logical)):
                walk(e.left)
                if getattr(e,'right',None) is not None: walk(e.right)
            elif isinstance(e,Conditional):
                walk(e.condition); walk(e.then_expr); walk(e.else_expr)
            elif isinstance(e,Call):
                for a in e.args: walk(a)
        walk(expr)
        return out

    needed=[]
    for expr in (filt.predicate.expr, sort.spec.expr, mp.expr, agg.expr):
        for f in fields(expr):
            if f not in needed: needed.append(f)
    if not needed:
        raise ValueError("native record-preserving pipeline requires numeric row fields")
    for f in needed:
        if not all(isinstance(r.get(f),(int,float)) and not isinstance(r.get(f),bool) for r in rows):
            raise ValueError(f"native record-preserving field '{f}' must be numeric")

    sort_fields=fields(sort.spec.expr)
    if len(sort_fields) != 1:
        raise ValueError("native record-preserving pipeline requires one numeric sort field")
    sort_field=sort_fields[0]

    def llvm_scalar(expr, refs, serial):
        if isinstance(expr,Literal) and isinstance(expr.value,(int,float)) and not isinstance(expr.value,bool):
            return f"{float(expr.value):.17e}"
        if isinstance(expr,(Field,Property)) and isinstance(expr.base,Name) and expr.base.name=='row':
            if expr.name not in refs: raise ValueError(f"unknown native row field '{expr.name}'")
            return refs[expr.name]
        if isinstance(expr,Name) and expr.name in {'item','value'}:
            raise ValueError("native record-preserving scalar map must use row fields")
        if isinstance(expr,Binary) and expr.op in {'+','-','*','/'}:
            a=llvm_scalar(expr.left,refs,serial); b=llvm_scalar(expr.right,refs,serial)
            v=f"%map_expr_{serial}_{len(lines)}"
            llvm_op={'+':'fadd','-':'fsub','*':'fmul','/':'fdiv'}[expr.op]
            lines.append(f"  {v} = {llvm_op} double {a}, {b}")
            return v
        raise ValueError("native record-preserving scalar map supports numeric row-field arithmetic")

    def llvm_pred(expr, refs, serial):
        if not isinstance(expr,Compare) or expr.op not in {'>','>=','<','<=','==','!='}:
            raise ValueError("native record-preserving filter supports one numeric comparison")
        a=llvm_scalar(expr.left,refs,serial); b=llvm_scalar(expr.right,refs,serial)
        pred={'>':'ogt','>=':'oge','<':'olt','<=':'ole','==':'oeq','!=':'one'}[expr.op]
        v=f"%pred_{serial}_{len(lines)}"
        lines.append(f"  {v} = fcmp {pred} double {a}, {b}")
        return v

    def c(v): return f"{float(v):.17e}"
    lines=["; ModuleID = 'slang-record-preserving-pipeline'", 'source_filename = "slang"', '']
    if function_part: lines.extend(function_part); lines.append('')
    cap=max(len(rows),1)
    for f in needed:
        vals=', '.join(f"double {c(r[f])}" for r in rows) or 'double 0.0'
        lines.append(f"@src_{f} = private constant [{cap} x double] [{vals}]")
    lines += ['', 'declare i32 @printf(ptr, ...)', '@fmt = private constant [7 x i8] c"%.17g\\0A\\00"', '', 'define i32 @main() {', 'entry:']

    # Materialize all needed fields in parallel buffers.
    bufs={f:f"%buf_{f}" for f in needed}
    for f in needed: lines.append(f"  {bufs[f]} = alloca [{cap} x double]")
    lines += ['  br label %copy_loop', 'copy_loop:', '  %copy_i = phi i64 [ 0, %entry ], [ %copy_next, %copy_body ]',
              f'  %copy_cond = icmp ult i64 %copy_i, {len(rows)}', '  br i1 %copy_cond, label %copy_body, label %filter_init', 'copy_body:']
    for f in needed:
        lines += [f'  %src_{f} = getelementptr [{cap} x double], ptr @src_{f}, i64 0, i64 %copy_i',
                  f'  %sv_{f} = load double, ptr %src_{f}',
                  f'  %dst_{f} = getelementptr [{cap} x double], ptr {bufs[f]}, i64 0, i64 %copy_i',
                  f'  store double %sv_{f}, ptr %dst_{f}']
    lines += ['  %copy_next = add i64 %copy_i, 1', '  br label %copy_loop', 'filter_init:', '  %fcnt_ptr = alloca i64', '  store i64 0, ptr %fcnt_ptr', '  br label %filter_loop', 'filter_loop:',
              '  %fi = phi i64 [ 0, %filter_init ], [ %fi_next, %filter_next ]',
              '  %fc = icmp ult i64 %fi, ' + str(len(rows)), '  br i1 %fc, label %filter_body, label %sort_init', 'filter_body:']
    refs={}
    for f in needed:
        refs[f]=f"%fval_{f}"
        lines += [f'  %fptr_{f} = getelementptr [{cap} x double], ptr {bufs[f]}, i64 0, i64 %fi', f'  %fval_{f} = load double, ptr %fptr_{f}']
    keep=llvm_pred(filt.predicate.expr,refs,1)
    # Keep all fields in lockstep while compacting the filtered rows.
    lines += [f'  br i1 {keep}, label %filter_keep, label %filter_next', 'filter_keep:', '  %keep_count = load i64, ptr %fcnt_ptr']
    for f in needed:
        lines += [f'  %keep_dst_{f} = getelementptr [{cap} x double], ptr {bufs[f]}, i64 0, i64 %keep_count', f'  store double %fval_{f}, ptr %keep_dst_{f}']
    lines += ['  %fnext_count = add i64 %keep_count, 1', '  store i64 %fnext_count, ptr %fcnt_ptr', '  br label %filter_next',
              'filter_next:', '  %fi_next = add i64 %fi, 1', '  br label %filter_loop', 'sort_init:', '  %n = load i64, ptr %fcnt_ptr', '  br label %outer', 'outer:',
              '  %oi = phi i64 [ 0, %sort_init ], [ %onext, %outer_advance ]', '  %olimit = sub i64 %n, 1', '  %oc = icmp ult i64 %oi, %olimit', '  br i1 %oc, label %inner_init, label %sort_done',
              'inner_init:', '  br label %inner', 'inner:', '  %j = phi i64 [ 0, %inner_init ], [ %jnext, %no_swap ]', '  %jlimit = sub i64 %n, 1', '  %jc = icmp ult i64 %j, %jlimit', '  br i1 %jc, label %inner_body, label %outer_advance', 'inner_body:',
              f'  %leftp = getelementptr [{cap} x double], ptr {bufs[sort_field]}, i64 0, i64 %j', '  %rj = add i64 %j, 1', f'  %rightp = getelementptr [{cap} x double], ptr {bufs[sort_field]}, i64 0, i64 %rj', '  %left = load double, ptr %leftp', '  %right = load double, ptr %rightp']
    cmp='ogt' if sort.spec.ascending else 'olt'
    lines += [f'  %swap = fcmp {cmp} double %left, %right', '  br i1 %swap, label %do_swap, label %no_swap', 'do_swap:']
    for f in needed:
        lines += [f'  %lp_{f} = getelementptr [{cap} x double], ptr {bufs[f]}, i64 0, i64 %j', f'  %rp_{f} = getelementptr [{cap} x double], ptr {bufs[f]}, i64 0, i64 %rj', f'  %lv_{f} = load double, ptr %lp_{f}', f'  %rv_{f} = load double, ptr %rp_{f}', f'  store double %rv_{f}, ptr %lp_{f}', f'  store double %lv_{f}, ptr %rp_{f}']
    lines += ['  br label %no_swap', 'no_swap:', '  %jnext = add i64 %j, 1', '  br label %inner', 'outer_advance:', '  %onext = add i64 %oi, 1', '  br label %outer', 'sort_done:',
              '  %acc = alloca double', '  %cnt = alloca i64', '  store i64 0, ptr %cnt']
    if agg.operation in {'min','max'}:
        init='0x7FF0000000000000' if agg.operation=='min' else '0xFFF0000000000000'
    else: init='0.00000000000000000e+00'
    lines += [f'  store double {init}, ptr %acc', '  br label %agg_loop', 'agg_loop:', '  %ai = phi i64 [ 0, %sort_done ], [ %anext, %agg_body ]', '  %ac = icmp ult i64 %ai, %n', '  br i1 %ac, label %agg_body, label %agg_done', 'agg_body:']
    refs={}
    for f in needed:
        refs[f]=f"%aval_{f}"
        lines += [f'  %ap_{f} = getelementptr [{cap} x double], ptr {bufs[f]}, i64 0, i64 %ai', f'  %aval_{f} = load double, ptr %ap_{f}']
    value=llvm_scalar(mp.expr,refs,2)
    cur='%cur'; lines.append(f'  {cur} = load double, ptr %acc')
    if agg.operation in {'sum','average','avg'}: lines.append(f'  %new = fadd double {cur}, {value}')
    elif agg.operation=='min': lines += [f'  %cmpv = fcmp ogt double {cur}, {value}', f'  %new = select i1 %cmpv, double {value}, double {cur}']
    elif agg.operation=='max': lines += [f'  %cmpv = fcmp olt double {cur}, {value}', f'  %new = select i1 %cmpv, double {value}, double {cur}']
    lines += ['  store double %new, ptr %acc', '  %ccur = load i64, ptr %cnt', '  %cnext = add i64 %ccur, 1', '  store i64 %cnext, ptr %cnt', '  %anext = add i64 %ai, 1', '  br label %agg_loop', 'agg_done:', '  %final = load double, ptr %acc']
    if agg.operation in {'average','avg'}:
        lines += ['  %cf = load i64, ptr %cnt', '  %cff = uitofp i64 %cf to double', '  %avg = fdiv double %final, %cff', '  call i32 (ptr, ...) @printf(ptr @fmt, double %avg)']
    else:
        lines += ['  call i32 (ptr, ...) @printf(ptr @fmt, double %final)']
    lines += ['  ret i32 0', '}']
    return '\n'.join(lines)

def aggregate_llvm_ir(p:Program, function_part=None, signatures=None, schema_contract=None):
    """Lower a numeric collection pipeline ending in an aggregate to LLVM IR.

    The native pipeline may contain filter/map/sort stages.  Sort is stable and
    deterministic, and the terminal aggregate consumes the sorted collection.
    The numeric subset intentionally keeps one scalar value per collection row.
    """
    validate(p)
    if p.bodies or p.simulation or p.ast.reduces:
        raise ValueError("native aggregate backend currently accepts data/filter/map/sort/aggregate programs")
    if signatures is None:
        signatures = {}
    aggs = list(p.ast.aggregates)
    if not aggs or p.ast.reduces:
        raise ValueError("native aggregate backend requires one or more aggregates and no reduce")
    if len({item.source for item in aggs}) != 1:
        raise ValueError("native multi-aggregate backend requires a shared collection source")
    allowed = {"sum", "count", "min", "max", "average", "avg", "any", "all"}
    if any(item.operation not in allowed for item in aggs):
        raise ValueError("native multi-aggregate backend received an unsupported terminal")
    agg = aggs[0]
    tables=p.data_tables or {}

    # Resolve one forward collection chain.  A sort is a normal pipeline stage
    # here rather than a terminal-only operation, which permits sort -> aggregate
    # and filter -> map -> sort -> aggregate without exposing implementation details.
    ordered=[]; available=set(tables)
    remaining=list(p.ast.filters)+list(p.ast.maps)+list(p.ast.sorts)
    while remaining:
        progress=False
        for op in remaining[:]:
            if op.source in available:
                ordered.append(op); available.add(op.result); remaining.remove(op); progress=True
        if not progress:
            raise ValueError("native aggregate backend requires a forward acyclic pipeline")
    if agg.source not in available:
        raise ValueError(f"unknown aggregate source '{agg.source}'")

    def field_for(expr):
        out=[]
        def walk(e):
            if isinstance(e,(Field,Property)) and isinstance(e.base,Name) and e.base.name=='row':
                out.append(e.name)
            elif isinstance(e,(Binary,Compare,Logical)):
                walk(e.left)
                if getattr(e,'right',None) is not None: walk(e.right)
            elif isinstance(e,Call):
                for arg in e.args: walk(arg)
        walk(expr)
        return out[0] if len(set(out))==1 else None

    globals_=[]; source_info={}
    # Track the semantic scalar field carried by each stage. Filters preserve
    # the current row field; maps produce a scalar value and therefore expose
    # ``item`` to later stages. This is especially important for
    # filter -> map -> sort -> aggregate pipelines using user functions.
    stage_fields={}
    for op in ordered:
        if op.source in tables and op.source not in source_info:
            if isinstance(op,FilterOp): expr=op.predicate.expr
            elif isinstance(op,MapOp): expr=op.expr
            elif isinstance(op,SortOp): expr=op.spec.expr
            else: raise ValueError("unsupported native aggregate pipeline stage")
            field=field_for(expr)
            if field is None:
                raise ValueError("native aggregate backend requires one numeric row field per source stage")
            vals=[]
            for row in tables[op.source]:
                v=row.get(field)
                if not isinstance(v,(int,float)):
                    raise ValueError(f"native collection field '{field}' in '{op.source}' must be numeric")
                vals.append(float(v))
            gname=f"data_{op.source}_{field}".replace('-','_')
            globals_.append((gname,vals)); source_info[op.source]=(gname,len(vals))
            stage_fields.setdefault(op.source, field)
        source_field = stage_fields.get(op.source)
        if isinstance(op, FilterOp):
            stage_fields[op.result] = source_field
        elif isinstance(op, MapOp):
            stage_fields[op.result] = None
        elif isinstance(op, SortOp):
            stage_fields[op.result] = source_field

    if agg.source in tables and agg.source not in source_info:
        field=field_for(agg.expr)
        if field is None and agg.operation != 'count':
            raise ValueError("native aggregate backend requires one numeric row field")
        vals=[]
        for row in tables[agg.source]:
            if agg.operation=='count': vals.append(1.0)
            else:
                v=row.get(field)
                if agg.operation in {'any', 'all'}:
                    if not isinstance(v, (bool, int, float)):
                        raise ValueError(f"native aggregate field '{field}' must be Boolean")
                    vals.append(1.0 if bool(v) else 0.0)
                else:
                    if not isinstance(v,(int,float)): raise ValueError(f"native aggregate field '{field}' must be numeric")
                    vals.append(float(v))
        gname=f"data_{agg.source}_{field or 'count'}".replace('-','_')
        globals_.append((gname,vals)); source_info[agg.source]=(gname,len(vals))

    lines=["; ModuleID = 'slang-aggregate'", 'source_filename = "slang"', '']
    if function_part:
        lines.extend(function_part); lines.append('')
    for gname,vals in globals_:
        elems=', '.join(f'double {v:.17e}' for v in vals) or 'double 0.0'
        lines.append(f'@{gname} = private constant [{len(vals) if vals else 1} x double] [{elems}]')
    lines += ['', 'declare i32 @printf(ptr, ...)', '@fmt = private constant [7 x i8] c"%.17g\\0A\\00"', '@fmt_bool = private constant [4 x i8] c"%s\\0A\\00"', '@agg_true = private constant [5 x i8] c"true\\00"', '@agg_false = private constant [6 x i8] c"false\\00"', '', 'define i32 @main() {', 'entry:']

    # Every intermediate stage owns a numeric buffer.  Sort receives its own
    # buffer because stable sorting is an in-place transformation.
    alloc={}; stage_index=0
    for op in ordered:
        stage_index += 1
        cap=(source_info[op.source][1] if op.source in source_info else alloc[op.source][2]) or 1
        alloc[op.result]=(f'%buf{stage_index}',f'%count{stage_index}',cap)
        lines += [f'  %buf{stage_index} = alloca [{cap} x double]', f'  %count{stage_index} = alloca i64']
    current='entry'
    if ordered:
        lines.append('  br label %entry0'); current='entry0'; lines.append('entry0:')

    desc={}
    for source,(gname,n) in source_info.items():
        ptr=f'getelementptr inbounds [{n if n else 1} x double], ptr @{gname}, i64 0, i64 0'
        desc[source]=(ptr,str(n),n)
    for op in ordered:
        buf,count,cap=alloc[op.result]
        desc[op.result]=(f'getelementptr [{cap} x double], ptr {buf}, i64 0, i64 0',count,cap)

    for i,op in enumerate(ordered,1):
        buf,count,cap=alloc[op.result]; srcptr,srccount,src_cap=desc[op.source]
        if isinstance(op,SortOp):
            # Copy source into the stage buffer, then perform deterministic
            # stable bubble sort.  This matches the existing native sort backend.
            lines += [f'  store i64 0, ptr {count}', f'  br label %copy_loop{i}', f'copy_loop{i}:',
                      f'  %copy_i{i} = phi i64 [ 0, %{current} ], [ %copy_next{i}, %copy_body{i} ]',
                      f'  %copy_src_count{i} = add i64 0, {srccount}' if srccount.isdigit() else f'  %copy_src_count{i} = load i64, ptr {srccount}',
                      f'  %copy_cond{i} = icmp ult i64 %copy_i{i}, %copy_src_count{i}',
                      f'  br i1 %copy_cond{i}, label %copy_body{i}, label %sort_outer_init{i}',
                      f'copy_body{i}:', f'  %copy_base{i} = {srcptr}', f'  %copy_src{i} = getelementptr double, ptr %copy_base{i}, i64 %copy_i{i}',
                      f'  %copy_v{i} = load double, ptr %copy_src{i}', f'  %copy_dst{i} = getelementptr [{cap} x double], ptr {buf}, i64 0, i64 %copy_i{i}',
                      f'  store double %copy_v{i}, ptr %copy_dst{i}', f'  %copy_next{i} = add i64 %copy_i{i}, 1', f'  br label %copy_loop{i}',
                      f'sort_outer_init{i}:']
            n_expr=srccount if srccount.isdigit() else f'%sort_n{i}'
            if not srccount.isdigit(): lines.append(f'  %sort_n{i} = load i64, ptr {srccount}')
            lines += [f'  br label %sort_outer{i}', f'sort_outer{i}:', f'  %outer_i{i} = phi i64 [ 0, %sort_outer_init{i} ], [ %outer_next{i}, %sort_outer_advance{i} ]',
                      f'  %outer_limit{i} = sub i64 {n_expr}, 1', f'  %outer_cond{i} = icmp ult i64 %outer_i{i}, %outer_limit{i}',
                      f'  br i1 %outer_cond{i}, label %sort_inner_init{i}, label %sort_done{i}', f'sort_inner_init{i}:', f'  br label %sort_inner{i}',
                      f'sort_inner{i}:', f'  %inner_j{i} = phi i64 [ 0, %sort_inner_init{i} ], [ %inner_next{i}, %sort_no_swap{i} ]',
                      f'  %inner_limit{i} = sub i64 {n_expr}, 1', f'  %inner_cond{i} = icmp ult i64 %inner_j{i}, %inner_limit{i}',
                      f'  br i1 %inner_cond{i}, label %sort_inner_body{i}, label %sort_outer_advance{i}', f'sort_inner_body{i}:',
                      f'  %left_ptr{i} = getelementptr [{cap} x double], ptr {buf}, i64 0, i64 %inner_j{i}',
                      f'  %right_j{i} = add i64 %inner_j{i}, 1', f'  %right_ptr{i} = getelementptr [{cap} x double], ptr {buf}, i64 0, i64 %right_j{i}',
                      f'  %left{i} = load double, ptr %left_ptr{i}', f'  %right{i} = load double, ptr %right_ptr{i}']
            cmp='ogt' if op.spec.ascending else 'olt'
            lines += [f'  %swap{i} = fcmp {cmp} double %left{i}, %right{i}', f'  br i1 %swap{i}, label %sort_do_swap{i}, label %sort_no_swap{i}',
                      f'sort_do_swap{i}:', f'  store double %right{i}, ptr %left_ptr{i}', f'  store double %left{i}, ptr %right_ptr{i}', f'  br label %sort_no_swap{i}',
                      f'sort_no_swap{i}:', f'  %inner_next{i} = add i64 %inner_j{i}, 1', f'  br label %sort_inner{i}',
                      f'sort_outer_advance{i}:', f'  %outer_next{i} = add i64 %outer_i{i}, 1', f'  br label %sort_outer{i}', f'sort_done{i}:']
            if srccount.isdigit(): lines.append(f'  store i64 {srccount}, ptr {count}')
            else: lines.append(f'  %sorted_count{i} = load i64, ptr {srccount}'); lines.append(f'  store i64 %sorted_count{i}, ptr {count}')
            current=f'sort_done{i}'
            continue

        loop=f'loop{i}'; body=f'body{i}'; done=f'done{i}'; skip=f'skip{i}'
        lines += [f'  store i64 0, ptr {count}', f'  br label %{loop}', f'{loop}:',
                  f'  %i{i} = phi i64 [ 0, %{current} ], [ %next{i}, %{skip} ]',
                  f'  %src_count{i} = add i64 0, {srccount}' if srccount.isdigit() else f'  %src_count{i} = load i64, ptr {srccount}',
                  f'  %cond{i} = icmp ult i64 %i{i}, %src_count{i}', f'  br i1 %cond{i}, label %{body}, label %{done}', f'{body}:',
                  f'  %base{i} = {srcptr}', f'  %srcptr{i} = getelementptr double, ptr %base{i}, i64 %i{i}', f'  %value{i} = load double, ptr %srcptr{i}']
        field_values = {}
        source_field = stage_fields.get(op.source)
        if source_field:
            field_values[source_field] = f"%value{i}"
        if isinstance(op,FilterOp):
            keep=_llvm_collection_predicate(op.predicate.expr,lines,i,signatures,field_values)
            lines += [f'  br i1 {keep}, label %keepblock{i}, label %{skip}', f'keepblock{i}:', f'  %oc{i} = load i64, ptr {count}',
                      f'  %dst{i} = getelementptr [{cap} x double], ptr {buf}, i64 0, i64 %oc{i}', f'  store double %value{i}, ptr %dst{i}',
                      f'  %on{i} = add i64 %oc{i}, 1', f'  store i64 %on{i}, ptr {count}', f'  br label %{skip}']
        else:
            expr=_llvm_scalar_expr(op.expr,srcptr,lines,i,signatures,field_values)
            lines += [f'  %dst{i} = getelementptr [{cap} x double], ptr {buf}, i64 0, i64 %i{i}', f'  store double {expr}, ptr %dst{i}', f'  br label %{skip}']
        lines += [f'{skip}:', f'  %next{i} = add i64 %i{i}, 1', f'  br label %{loop}', f'{done}:']
        if isinstance(op,MapOp):
            if srccount.isdigit(): lines.append(f'  store i64 {srccount}, ptr {count}')
            else: lines.append(f'  %map_source_count{i} = load i64, ptr {srccount}'); lines.append(f'  store i64 %map_source_count{i}, ptr {count}')
        current=done

    srcptr,srccount,cap=desc[agg.source]
    # All terminal results share the same materialized pipeline.  Maintain one
    # accumulator per requested operation and update them in a single pass.
    for j, item in enumerate(aggs):
        if item.operation in {"any", "all"}:
            lines += [f'  %aggaccb{j} = alloca i1', f'  store i1 {"false" if item.operation == "any" else "true"}, ptr %aggaccb{j}']
        else:
            init = '0x7FF0000000000000' if item.operation == 'min' else '0xFFF0000000000000' if item.operation == 'max' else '0.00000000000000000e+00'
            lines += [f'  %aggacc{j} = alloca double', f'  store double {init}, ptr %aggacc{j}']
    lines += ['  %aggcnt = alloca i64', '  store i64 0, ptr %aggcnt', '  br label %agg_loop', 'agg_loop:',
              '  %ai = phi i64 [ 0, %'+current+' ], [ %anext, %agg_body ]',
              f'  %acond = icmp ult i64 %ai, {srccount}' if srccount.isdigit() else f'  %asrcount = load i64, ptr {srccount}\n  %acond = icmp ult i64 %ai, %asrcount',
              '  br i1 %acond, label %agg_body, label %agg_done', 'agg_body:', f'  %abase = {srcptr}',
              '  %aptr = getelementptr double, ptr %abase, i64 %ai', '  %av = load double, ptr %aptr']
    for j, item in enumerate(aggs):
        op = item.operation
        if op in {'any', 'all'}:
            lines += [f'  %abool{j} = fcmp one double %av, 0.00000000000000000e+00', f'  %acur{j} = load i1, ptr %aggaccb{j}',
                      f'  %anew{j} = {"or" if op == "any" else "and"} i1 %acur{j}, %abool{j}', f'  store i1 %anew{j}, ptr %aggaccb{j}']
        else:
            lines.append(f'  %acur{j} = load double, ptr %aggacc{j}')
            if op in {'sum', 'average', 'avg'}:
                lines.append(f'  %anew{j} = fadd double %acur{j}, %av')
            elif op == 'count':
                lines.append(f'  %anew{j} = fadd double %acur{j}, 1.00000000000000000e+00')
            elif op == 'max':
                lines += [f'  %acmp{j} = fcmp olt double %acur{j}, %av', f'  %anew{j} = select i1 %acmp{j}, double %av, double %acur{j}']
            elif op == 'min':
                lines += [f'  %acmp{j} = fcmp ogt double %acur{j}, %av', f'  %anew{j} = select i1 %acmp{j}, double %av, double %acur{j}']
            lines.append(f'  store double %anew{j}, ptr %aggacc{j}')
    lines += ['  %ccur = load i64, ptr %aggcnt', '  %cnext = add i64 %ccur, 1', '  store i64 %cnext, ptr %aggcnt',
              '  %anext = add i64 %ai, 1', '  br label %agg_loop', 'agg_done:']
    for j, item in enumerate(aggs):
        op = item.operation
        if op in {'any', 'all'}:
            lines += [f'  %finalb{j} = load i1, ptr %aggaccb{j}', f'  %bool_text{j} = select i1 %finalb{j}, ptr @agg_true, ptr @agg_false',
                      f'  call i32 (ptr, ...) @printf(ptr @fmt_bool, ptr %bool_text{j})']
        else:
            lines.append(f'  %final{j} = load double, ptr %aggacc{j}')
            if op in {'average', 'avg'}:
                lines += [f'  %finalcount{j} = load i64, ptr %aggcnt', f'  %finalcountf{j} = uitofp i64 %finalcount{j} to double',
                          f'  %avg{j} = fdiv double %final{j}, %finalcountf{j}', f'  call i32 (ptr, ...) @printf(ptr @fmt, double %avg{j})']
            else:
                lines.append(f'  call i32 (ptr, ...) @printf(ptr @fmt, double %final{j})')
    lines += ['  ret i32 0', '}']
    return '\n'.join(lines)

    lines += [f'  %aggacc = alloca double', f'  %aggcnt = alloca i64', '  store i64 0, ptr %aggcnt']
    if agg.operation in {'max','min'}:
        init='0x7FF0000000000000' if agg.operation=='min' else '0xFFF0000000000000'
    else: init='0.00000000000000000e+00'
    lines += [f'  store double {init}, ptr %aggacc', '  br label %agg_loop', 'agg_loop:', '  %ai = phi i64 [ 0, %'+current+' ], [ %anext, %agg_body ]',
              f'  %acond = icmp ult i64 %ai, {srccount}' if srccount.isdigit() else f'  %asrcount = load i64, ptr {srccount}\n  %acond = icmp ult i64 %ai, %asrcount',
              '  br i1 %acond, label %agg_body, label %agg_done', 'agg_body:', f'  %abase = {srcptr}', '  %aptr = getelementptr double, ptr %abase, i64 %ai', '  %av = load double, ptr %aptr', '  %acur = load double, ptr %aggacc']
    if agg.operation=='sum' or agg.operation in {'average','avg'}: lines += ['  %anew = fadd double %acur, %av']
    elif agg.operation=='count': lines += ['  %anew = fadd double %acur, 1.00000000000000000e+00']
    elif agg.operation=='max': lines += ['  %acmp = fcmp olt double %acur, %av', '  %anew = select i1 %acmp, double %av, double %acur']
    elif agg.operation=='min': lines += ['  %acmp = fcmp ogt double %acur, %av', '  %anew = select i1 %acmp, double %av, double %acur']
    else: raise ValueError(f"unsupported native aggregate '{agg.operation}'")
    lines += ['  store double %anew, ptr %aggacc', '  %ccur = load i64, ptr %aggcnt', '  %cnext = add i64 %ccur, 1', '  store i64 %cnext, ptr %aggcnt', '  %anext = add i64 %ai, 1', '  br label %agg_loop',
              'agg_done:', '  %final = load double, ptr %aggacc']
    if agg.operation in {'average','avg'}:
        lines += ['  %finalcount = load i64, ptr %aggcnt', '  %finalcountf = uitofp i64 %finalcount to double', '  %avg = fdiv double %final, %finalcountf', '  call i32 (ptr, ...) @printf(ptr @fmt, double %avg)']
    else: lines += ['  call i32 (ptr, ...) @printf(ptr @fmt, double %final)']
    lines += ['  ret i32 0', '}']
    return '\n'.join(lines)

def fused_aggregate_llvm_ir(p:Program, function_part=None, signatures=None):
    """Lower a filter/map pipeline with one shared scan for many aggregates."""
    validate(p)
    if p.bodies or p.simulation or p.ast.reduces or p.ast.sorts:
        raise ValueError("native fused backend accepts data/filter/map/aggregate programs")
    aggs = list(p.ast.aggregates)
    if not aggs:
        raise ValueError("native fused backend requires at least one aggregate")
    if len({item.source for item in aggs}) != 1:
        raise ValueError("native fused multi-aggregate backend requires a shared collection source")
    allowed = {"sum", "count", "min", "max", "average", "avg", "any", "all"}
    if any(item.operation not in allowed for item in aggs):
        raise ValueError("native fused multi-aggregate backend received an unsupported terminal")
    tables = dict(p.data_tables or {})
    signatures = signatures or {}
    # Numeric list literals are ordinary S-Lang collections too.  Normalize
    # them to the same one-column row representation used by data-table input.
    record_fields = {decl.name: [name for name, _type in decl.fields] for decl in p.ast.records}
    for binding in p.ast.bindings:
        if binding.name in tables or not isinstance(binding.expr, Literal) or not isinstance(binding.expr.value, list):
            continue
        values = binding.expr.value
        if all(isinstance(value, Literal) and isinstance(value.value, (int, float, bool)) for value in values):
            tables[binding.name] = [{"value": value.value} for value in values]
            continue
        # Materialize literal Record collections into row dictionaries so the
        # same versioned lowering can handle ordinary record lists as well.
        if values and all(isinstance(value, Call) and value.name in record_fields for value in values):
            materialized = []
            for value in values:
                names = record_fields[value.name]
                if len(names) != len(value.args):
                    raise ValueError(f"native fused record '{value.name}' has an invalid constructor arity")
                row = {}
                for field_name, argument in zip(names, value.args):
                    if not isinstance(argument, Literal) or not isinstance(argument.value, (int, float, bool, str)):
                        raise ValueError("native fused record literals require scalar literal fields")
                    row[field_name] = argument.value
                materialized.append(row)
            tables[binding.name] = materialized

    # Reassigned collection names are SSA-versioned before lowering.  The AST
    # stores filters and maps in separate lists, so concatenating those lists
    # loses source order (and a self-rebinding stage such as `x = x map ...`
    # otherwise creates an apparent cycle in the backend's name lookup).
    raw_stages = list(p.ast.filters) + list(p.ast.maps)
    raw_stages.sort(key=lambda op: (
        source_span_of(op).start.line if source_span_of(op) else 10**9,
        source_span_of(op).start.column if source_span_of(op) else 10**9,
    ))
    latest = {}
    ordered = []
    for index, op in enumerate(raw_stages, 1):
        source = latest.get(op.source, op.source)
        result = f"__slang_collection_stage_{index}"
        ordered.append(replace(op, source=source, result=result))
        latest[op.result] = result
    aggs = [replace(item, source=latest.get(item.source, item.source)) for item in aggs]
    available = set(tables)
    for op in ordered:
        if op.source not in available:
            raise ValueError("native fused backend requires a forward acyclic pipeline")
        available.add(op.result)
    source_name = aggs[0].source
    if source_name not in available:
        raise ValueError(f"unknown aggregate source '{source_name}'")
    by_result = {op.result: op for op in ordered}
    chain = []
    cur = source_name
    while cur in by_result:
        op = by_result[cur]; chain.append(op); cur = op.source
    chain.reverse()
    if cur not in tables:
        raise ValueError("native fused backend requires a literal data source")
    source = cur
    rows = tables[source]

    fields = set()
    def collect(expr):
        if isinstance(expr, (Field, Property)) and isinstance(expr.base, Name) and expr.base.name == "row":
            fields.add(expr.name)
        elif isinstance(expr, (Binary, Compare, Logical)):
            collect(expr.left)
            if getattr(expr, "right", None) is not None: collect(expr.right)
        elif isinstance(expr, Conditional):
            collect(expr.condition); collect(expr.then_expr); collect(expr.else_expr)
        elif isinstance(expr, Call):
            for a in expr.args: collect(a)
    for stage in chain:
        collect(stage.predicate.expr if isinstance(stage, FilterOp) else stage.expr)
    for item in aggs:
        if item.operation != "count":
            collect(item.expr)

    def uses_current_item(expr):
        if isinstance(expr, Name):
            return expr.name in {"item", "value"}
        if isinstance(expr, (Binary, Compare, Logical)):
            return uses_current_item(expr.left) or (getattr(expr, "right", None) is not None and uses_current_item(expr.right))
        if isinstance(expr, Conditional):
            return uses_current_item(expr.condition) or uses_current_item(expr.then_expr) or uses_current_item(expr.else_expr)
        if isinstance(expr, Call):
            return any(uses_current_item(arg) for arg in expr.args)
        return False

    # `item` refers to the original scalar source only before the first map.
    # After a map it refers to the current pipeline value, not a synthetic
    # source column named `value` (which would be absent from Record rows).
    seen_map = False
    needs_source_value = False
    for stage in chain:
        stage_expr = stage.predicate.expr if isinstance(stage, FilterOp) else stage.expr
        if isinstance(stage, MapOp):
            seen_map = True
        elif not seen_map and uses_current_item(stage_expr):
            needs_source_value = True
    if not seen_map and any(item.operation != "count" and uses_current_item(item.expr) for item in aggs):
        needs_source_value = True
    if needs_source_value:
        fields.add("value")

    module_name = "slang-fused-aggregate" if len(aggs) == 1 else "slang-fused-multi-aggregate"
    lines = [f"; ModuleID = '{module_name}'", 'source_filename = "slang"', '']
    if function_part:
        lines.extend(function_part); lines.append('')
    field_arrays = {}
    for field in sorted(fields):
        vals = [row.get(field) for row in rows]
        if not all(isinstance(v, (int, float, bool)) for v in vals):
            raise ValueError(f"native fused field '{field}' must be numeric or Boolean")
        g = f"data_{source}_{field}".replace("-", "_")
        field_arrays[field] = g
        elems = ', '.join(f'double {float(v):.17e}' for v in vals) or 'double 0.0'
        lines.append(f"@{g} = private constant [{len(vals) if vals else 1} x double] [{elems}]")
    lines += ['', 'declare i32 @printf(ptr, ...)', '@fmt = private constant [7 x i8] c"%.17g\\0A\\00"',
              '@fmt_bool = private constant [4 x i8] c"%s\\0A\\00"',
              '@empty_msg = private constant [49 x i8] c"aggregate cannot operate on an empty collection\\0A\\00"',
              '@agg_true = private constant [5 x i8] c"true\\00"',
              '@agg_false = private constant [6 x i8] c"false\\00"', '', 'define i32 @main() {', 'entry:']

    def scalar_expr(expr, value_ref, serial):
        if isinstance(expr, Literal) and isinstance(expr.value, (int, float, bool)):
            return f"{float(expr.value):.17e}"
        if isinstance(expr, Name) and expr.name in {"item", "value"}:
            return value_ref
        if isinstance(expr, (Field, Property)) and isinstance(expr.base, Name) and expr.base.name == "row":
            if expr.name not in field_arrays:
                raise ValueError(f"unknown native row field '{expr.name}'")
            return f"%row_{expr.name}"
        if isinstance(expr, Binary) and expr.op in {"+", "-", "*", "/", "%"}:
            a = scalar_expr(expr.left, value_ref, serial)
            b = scalar_expr(expr.right, value_ref, serial)
            name = f"%expr_{serial}_{len(lines)}"
            llvm_op = {"+":"fadd", "-":"fsub", "*":"fmul", "/":"fdiv", "%":"frem"}[expr.op]
            lines.append(f"  {name} = {llvm_op} double {a}, {b}")
            return name
        if isinstance(expr, Call) and expr.name in signatures:
            params, result = signatures[expr.name]
            if result != "double":
                raise ValueError(f"fused native aggregate requires numeric function '{expr.name}'")
            if len(params) != len(expr.args):
                raise ValueError(f"native function '{expr.name}' expects {len(params)} argument(s)")
            args=[]
            for arg, expected in zip(expr.args, params):
                if expected != "double":
                    raise ValueError(f"native aggregate function '{expr.name}' requires numeric arguments")
                args.append(f"double {scalar_expr(arg, value_ref, serial)}")
            name=f"%call_{serial}_{len(lines)}"
            lines.append(f"  {name} = call double @{expr.name}({', '.join(args)})")
            return name
        raise ValueError("fused native backend supports numeric literals, item, row fields, arithmetic and numeric function calls")

    def predicate(expr, value_ref, serial):
        if isinstance(expr, Logical):
            if expr.op == "not":
                inner = predicate(expr.left, value_ref, serial)
                name = f"%keep_not_{serial}_{len(lines)}"
                lines.append(f"  {name} = xor i1 {inner}, true")
                return name
            if expr.op in {"and", "or"}:
                left = predicate(expr.left, value_ref, serial)
                right = predicate(expr.right, value_ref, serial)
                name = f"%keep_{expr.op}_{serial}_{len(lines)}"
                lines.append(f"  {name} = {expr.op} i1 {left}, {right}")
                return name
            raise ValueError("fused native filter supports and/or/not Boolean predicates")
        if isinstance(expr, Call) and expr.name in signatures:
            params, result = signatures[expr.name]
            if result != "i1":
                raise ValueError(f"fused native filter requires Boolean function '{expr.name}'")
            if len(params) != len(expr.args):
                raise ValueError(f"native function '{expr.name}' expects {len(params)} argument(s)")
            args=[]
            for arg, expected in zip(expr.args, params):
                if expected != "double":
                    raise ValueError(f"native filter function '{expr.name}' requires numeric arguments")
                args.append(f"double {scalar_expr(arg, value_ref, serial)}")
            name=f"%keep_call_{serial}_{len(lines)}"
            lines.append(f"  {name} = call i1 @{expr.name}({', '.join(args)})")
            return name
        if not isinstance(expr, Compare) or expr.op not in {">", ">=", "<", "<=", "==", "!="}:
            raise ValueError("fused native filter supports numeric comparison, Boolean function call, and logical composition")
        a = scalar_expr(expr.left, value_ref, serial)
        b = scalar_expr(expr.right, value_ref, serial)
        pred = {">":"ogt", ">=":"oge", "<":"olt", "<=":"ole", "==":"oeq", "!=":"one"}[expr.op]
        name = f"%keep_{serial}_{len(lines)}"
        lines.append(f"  {name} = fcmp {pred} double {a}, {b}")
        return name

    for j, item in enumerate(aggs):
        op = item.operation
        if op in {"any", "all"}:
            init = "false" if op == "any" else "true"
            lines += [f"  %accb{j} = alloca i1", f"  store i1 {init}, ptr %accb{j}"]
        else:
            init = "0x7FF0000000000000" if op == "min" else "0xFFF0000000000000" if op == "max" else "0.00000000000000000e+00"
            lines += [f"  %acc{j} = alloca double", f"  store double {init}, ptr %acc{j}"]
    lines += ["  %cnt = alloca i64", "  store i64 0, ptr %cnt", "  br label %loop", "loop:",
              f"  %i = phi i64 [ 0, %entry ], [ %next_i, %advance ]",
              f"  %cond = icmp ult i64 %i, {len(rows)}", "  br i1 %cond, label %body, label %done", "body:"]
    for field, g in sorted(field_arrays.items()):
        n = len(rows) if rows else 1
        lines.append(f"  %ptr_{field} = getelementptr inbounds [{n} x double], ptr @{g}, i64 0, i64 %i")
        lines.append(f"  %row_{field} = load double, ptr %ptr_{field}")

    current_value = "%row_value" if "value" in field_arrays else None
    serial = 0
    for stage in chain:
        serial += 1
        if isinstance(stage, FilterOp):
            keep = predicate(stage.predicate.expr, current_value or "%row_value", serial)
            lines += [f"  br i1 {keep}, label %filter_pass_{serial}, label %advance", f"filter_pass_{serial}:"]
        else:
            current_value = scalar_expr(stage.expr, current_value or "%row_value", serial)

    for j, item in enumerate(aggs):
        op = item.operation
        if op == "count":
            continue
        serial += 1
        value = scalar_expr(item.expr, current_value or "%row_value", serial)
        if op in {"any", "all"}:
            lines += [f"  %boolv{j} = fcmp one double {value}, 0.00000000000000000e+00",
                      f"  %oldb{j} = load i1, ptr %accb{j}",
                      f"  %newb{j} = {'or' if op == 'any' else 'and'} i1 %oldb{j}, %boolv{j}",
                      f"  store i1 %newb{j}, ptr %accb{j}"]
        else:
            lines.append(f"  %old{j} = load double, ptr %acc{j}")
            if op in {"sum", "average", "avg"}:
                lines.append(f"  %new{j} = fadd double %old{j}, {value}")
            elif op == "min":
                lines += [f"  %cmp{j} = fcmp ogt double %old{j}, {value}", f"  %new{j} = select i1 %cmp{j}, double {value}, double %old{j}"]
            elif op == "max":
                lines += [f"  %cmp{j} = fcmp olt double %old{j}, {value}", f"  %new{j} = select i1 %cmp{j}, double {value}, double %old{j}"]
            lines.append(f"  store double %new{j}, ptr %acc{j}")
    lines += ["  %oldcnt = load i64, ptr %cnt", "  %newcnt = add i64 %oldcnt, 1", "  store i64 %newcnt, ptr %cnt",
              "  br label %advance", "advance:", "  %next_i = add i64 %i, 1", "  br label %loop", "done:",
              "  %finalcnt = load i64, ptr %cnt"]
    if any(item.operation in {"min", "max", "average", "avg"} for item in aggs):
        # Match interpreter semantics: extrema and averages are undefined
        # when filtering removes every row.
        lines += ["  %has_rows = icmp ne i64 %finalcnt, 0",
                  "  br i1 %has_rows, label %aggregate_results, label %aggregate_empty",
                  "aggregate_empty:",
                  "  call i32 (ptr, ...) @printf(ptr @empty_msg)",
                  "  ret i32 1",
                  "aggregate_results:"]
    for j, item in enumerate(aggs):
        op = item.operation
        if op in {"any", "all"}:
            lines += [f"  %finalb{j} = load i1, ptr %accb{j}", f"  %textb{j} = select i1 %finalb{j}, ptr @agg_true, ptr @agg_false",
                      f"  call i32 (ptr, ...) @printf(ptr @fmt_bool, ptr %textb{j})"]
        elif op == "count":
            lines += [f"  %count_value{j} = uitofp i64 %finalcnt to double", f"  call i32 (ptr, ...) @printf(ptr @fmt, double %count_value{j})"]
        else:
            lines.append(f"  %final{j} = load double, ptr %acc{j}")
            if op in {"average", "avg"}:
                lines += [f"  %countf{j} = uitofp i64 %finalcnt to double", f"  %avg{j} = fdiv double %final{j}, %countf{j}",
                          f"  call i32 (ptr, ...) @printf(ptr @fmt, double %avg{j})"]
            else:
                lines.append(f"  call i32 (ptr, ...) @printf(ptr @fmt, double %final{j})")
    lines += ["  ret i32 0", "}", ""]
    return '\n'.join(lines)

def fused_reduce_llvm_ir(p:Program):
    """Lower filter/map -> reduce as one deterministic native pass.

    The reducer is intentionally restricted to ``acc <op> current``. The
    current value may be the source row value/field or the scalar produced by
    an upstream map. This preserves the reduction order and therefore does not
    assume associative or commutative arithmetic.
    """
    validate(p)
    if len(p.ast.reduces) != 1:
        raise ValueError("native fused reduce requires exactly one reduce operation")
    if p.bodies or p.simulation or p.ast.sorts or p.ast.aggregates or len(p.ast.reduces) != 1:
        raise ValueError("native fused reduce accepts data/filter/map/reduce programs")
    red = p.ast.reduces[0]
    tables = p.data_tables or {}

    available = set(tables)
    remaining = list(p.ast.filters) + list(p.ast.maps)
    ordered=[]
    while remaining:
        progress=False
        for op in remaining[:]:
            if op.source in available:
                ordered.append(op); available.add(op.result); remaining.remove(op); progress=True
        if not progress:
            raise ValueError("native fused reduce requires a forward acyclic pipeline")
    if red.source not in available:
        raise ValueError(f"unknown reduce source '{red.source}'")
    by_result={op.result: op for op in ordered}
    chain=[]; cur=red.source
    while cur in by_result:
        op=by_result[cur]; chain.append(op); cur=op.source
    chain.reverse()
    if cur not in tables:
        raise ValueError("native fused reduce requires a literal data source")
    source=cur; rows=tables[source]
    if not isinstance(red.initial, Literal) or not isinstance(red.initial.value,(int,float)):
        raise ValueError("native fused reduce requires a numeric literal initial accumulator")
    if not isinstance(red.expr, Binary) or not isinstance(red.expr.left, Name) or red.expr.left.name != "acc" or red.expr.op not in {"+","-","*","/"}:
        raise ValueError("native fused reduce supports only 'acc <+|-|*|/> current'")
    rhs=red.expr.right
    if isinstance(rhs, Name) and rhs.name == "item":
        rhs_kind="current"
    elif isinstance(rhs, Field) and isinstance(rhs.base, Name) and rhs.base.name == "row":
        rhs_kind=rhs.name
    else:
        raise ValueError("native fused reduce supports current item or one numeric row field")

    fields=set()
    def collect(expr):
        if isinstance(expr,Field) and isinstance(expr.base,Name) and expr.base.name=="row": fields.add(expr.name)
        elif isinstance(expr,(Binary,Compare,Logical)):
            collect(expr.left)
            if getattr(expr,"right",None) is not None: collect(expr.right)
    for stage in chain:
        collect(stage.predicate.expr if isinstance(stage,FilterOp) else stage.expr)
    if rhs_kind != "current": fields.add(rhs_kind)
    lines=["; ModuleID = 'slang-fused-reduce'", 'source_filename = "slang"', '']
    arrays={}
    for field in sorted(fields):
        vals=[row.get(field) for row in rows]
        if not all(isinstance(v,(int,float)) for v in vals):
            raise ValueError(f"native fused reduce field '{field}' must be numeric")
        g=f"data_{source}_{field}".replace('-','_'); arrays[field]=g
        elems=', '.join(f'double {float(v):.17e}' for v in vals) or 'double 0.0'
        lines.append(f"@{g} = private constant [{len(vals) if vals else 1} x double] [{elems}]")
    lines += ['', 'declare i32 @printf(ptr, ...)', 'declare double @llvm.pow.f64(double, double)', '@fmt = private constant [7 x i8] c"%.17g\\0A\\00"', '', 'define i32 @main() {', 'entry:',
              '  %acc = alloca double', f'  store double {float(red.initial.value):.17e}, ptr %acc',
              '  br label %loop', 'loop:', f'  %i = phi i64 [ 0, %entry ], [ %next, %advance ]',
              f'  %cond = icmp ult i64 %i, {len(rows)}', '  br i1 %cond, label %body, label %done', 'body:']
    for field,g in sorted(arrays.items()):
        n=len(rows) if rows else 1
        lines += [f'  %ptr_{field} = getelementptr inbounds [{n} x double], ptr @{g}, i64 0, i64 %i', f'  %row_{field} = load double, ptr %ptr_{field}']
    def scalar(expr, current, serial):
        if isinstance(expr,Literal) and isinstance(expr.value,(int,float)): return f'{float(expr.value):.17e}'
        if isinstance(expr,Name) and expr.name=='item': return current
        if isinstance(expr,Field) and isinstance(expr.base,Name) and expr.base.name=='row':
            return f'%row_{expr.name}'
        if isinstance(expr,Binary) and expr.op in {'+','-','*','/','^','%'}:
            a=scalar(expr.left,current,serial); b=scalar(expr.right,current,serial); name=f'%expr_{serial}_{len(lines)}'
            if expr.op == '^':
                lines.append(f"  {name} = call double @llvm.pow.f64(double {a}, double {b})")
            else:
                llvm_op = {"+":"fadd", "-":"fsub", "*":"fmul", "/":"fdiv", "%":"frem"}[expr.op]
                lines.append(f"  {name} = {llvm_op} double {a}, {b}")
            return name
        raise ValueError("native fused reduce supports numeric literals, item, row fields and arithmetic")
    def pred(expr,current,serial):
        if not isinstance(expr,Compare) or expr.op not in {'>','>=','<','<=','==','!='}:
            raise ValueError("native fused filter supports a single numeric comparison")
        a=scalar(expr.left,current,serial); b=scalar(expr.right,current,serial); name=f'%keep_{serial}_{len(lines)}'
        cmp={'>' :'ogt','>=':'oge','<':'olt','<=':'ole','==':'oeq','!=':'one'}[expr.op]
        lines.append(f'  {name} = fcmp {cmp} double {a}, {b}')
        return name
    current='%row_value' if 'value' in arrays else (f'%row_{sorted(arrays)[0]}' if arrays else '0.00000000000000000e+00')
    serial=0
    for stage in chain:
        serial += 1
        if isinstance(stage,FilterOp):
            keep=pred(stage.predicate.expr,current,serial)
            lines += [f'  br i1 {keep}, label %pass_{serial}, label %advance', f'pass_{serial}:']
        else:
            current=scalar(stage.expr,current,serial)
    rhs_value=current if rhs_kind=='current' else f'%row_{rhs_kind}'
    cur_acc='%cur_acc'; lines.append(f'  {cur_acc} = load double, ptr %acc')
    op=red.expr.op; inst={'+':'fadd','-':'fsub','*':'fmul','/':'fdiv'}[op]
    lines.append(f'  %new_acc = {inst} double {cur_acc}, {rhs_value}')
    lines += ['  store double %new_acc, ptr %acc', '  br label %advance', 'advance:', '  %next = add i64 %i, 1', '  br label %loop', 'done:',
              '  %final = load double, ptr %acc', '  call i32 (ptr, ...) @printf(ptr @fmt, double %final)', '  ret i32 0', '}']
    return '\n'.join(lines)


def pipeline_sort_reduce_llvm_ir(p:Program, function_part=None, signatures=None):
    """Lower filter/map -> stable sort -> reduce as one native numeric pipeline."""
    validate(p)
    if len(p.ast.sorts) != 1 or len(p.ast.reduces) != 1:
        raise ValueError("native pipeline sort-reduce backend requires exactly one sort and one reduce")
    if p.ast.aggregates or p.bodies or p.simulation:
        raise ValueError("native pipeline sort-reduce backend accepts data/filter/map/sort/reduce programs")
    if signatures is None:
        signatures = {}
    sort = p.ast.sorts[0]
    red = p.ast.reduces[0]
    if red.source != sort.result:
        raise ValueError("native pipeline sort-reduce requires reduce to consume the sorted collection")
    tables = p.data_tables or {}

    # Resolve the forward collection chain ending at the sort.
    available=set(tables); remaining=list(p.ast.filters)+list(p.ast.maps)
    ordered=[]
    while remaining:
        progress=False
        for op in remaining[:]:
            if op.source in available:
                ordered.append(op); available.add(op.result); remaining.remove(op); progress=True
        if not progress:
            raise ValueError("native pipeline sort-reduce requires a forward acyclic pipeline")
    if sort.source not in available:
        raise ValueError(f"unknown sort source '{sort.source}'")

    def field_for(expr):
        out=[]
        def walk(e):
            if isinstance(e,(Field,Property)) and isinstance(e.base,Name) and e.base.name=='row': out.append(e.name)
            elif isinstance(e,(Binary,Compare,Logical)):
                walk(e.left)
                if getattr(e,'right',None) is not None: walk(e.right)
            elif isinstance(e,Call):
                for a in e.args: walk(a)
        walk(expr)
        return out[0] if len(set(out))==1 else None

    # All native stages currently operate on one numeric scalar per row.
    source_fields={}
    for op in ordered:
        expr=op.predicate.expr if isinstance(op,FilterOp) else op.expr
        field=field_for(expr)
        if field is None:
            raise ValueError("native pipeline sort-reduce requires one numeric row field per stage")
        source_fields.setdefault(op.source, field)
    sort_field=field_for(sort.spec.expr)
    if sort_field is None and isinstance(sort.spec.expr, Name) and sort.spec.expr.name in {'item','value'}:
        # A map stage produces scalar items, so `sort by item`/`sort by value`
        # refers to that scalar rather than a record field.
        sort_field=next(iter(source_fields.values()), None)
    if sort_field is None:
        raise ValueError("native pipeline sort-reduce requires one numeric sort field")
    red_rhs=red.expr.right if isinstance(red.expr, Binary) else None
    if not isinstance(red.initial, Literal) or not isinstance(red.initial.value,(int,float)):
        raise ValueError("native pipeline sort-reduce requires a numeric literal initial accumulator")
    if not isinstance(red.expr,Binary) or not isinstance(red.expr.left,Name) or red.expr.left.name!='acc' or red.expr.op not in {'+','-','*','/'}:
        raise ValueError("native pipeline sort-reduce supports only 'acc <+|-|*|/> value'")
    if isinstance(red_rhs,Name) and red_rhs.name in {'item','value'}:
        red_field=sort_field
    elif isinstance(red_rhs,(Field,Property)) and isinstance(red_rhs.base,Name) and red_rhs.base.name=='row':
        red_field=red_rhs.name
    else:
        raise ValueError("native pipeline sort-reduce requires item or one numeric row field")
    if red_field != sort_field:
        raise ValueError("native pipeline sort-reduce requires sort and reduce to use the same numeric field")

    # Materialize only literal data sources. Intermediate stages use compiler-generated buffers.
    globals_=[]; source_info={}
    for op in ordered+[sort]:
        if op.source in tables and op.source not in source_info:
            field=source_fields.get(op.source, sort_field)
            vals=[]
            for row in tables[op.source]:
                v=row.get(field)
                if not isinstance(v,(int,float)):
                    raise ValueError(f"native collection field '{field}' in '{op.source}' must be numeric")
                vals.append(float(v))
            gname=f"data_{op.source}_{field}".replace('-','_')
            globals_.append((gname,vals)); source_info[op.source]=(gname,len(vals))

    lines=["; ModuleID = 'slang-pipeline-sort-reduce'", 'source_filename = "slang"', '']
    if function_part:
        lines.extend(function_part); lines.append('')
    for gname,vals in globals_:
        cap=max(len(vals),1); elems=', '.join(f'double {v:.17e}' for v in vals) or 'double 0.0'
        lines.append(f'@{gname} = private constant [{cap} x double] [{elems}]')
    lines += ['', 'declare double @slang_reduce_f64(ptr, i64, double, i32)', 'declare i32 @printf(ptr, ...)', '@fmt = private constant [7 x i8] c"%.15g\\0A\\00"', '', 'define i32 @main() {', 'entry:']

    # Allocate one buffer for each pre-sort stage and one for the sorted result.
    alloc={}
    stages=ordered+[sort]
    for i,op in enumerate(stages,1):
        cap=(source_info[op.source][1] if op.source in source_info else alloc[op.source][2]) or 1
        alloc[op.result]=(f'%buf{i}',f'%count{i}',cap)
        lines += [f'  %buf{i} = alloca [{cap} x double]', f'  %count{i} = alloca i64']

    desc={}
    for source,(gname,n) in source_info.items():
        cap=max(n,1); ptr=f'getelementptr inbounds [{cap} x double], ptr @{gname}, i64 0, i64 0'
        desc[source]=(ptr,str(n),n)
    current='entry'
    if stages:
        lines += ['  br label %pipeline0', 'pipeline0:']
    for i,op in enumerate(stages,1):
        buf,count,cap=alloc[op.result]
        srcptr,srccount,src_cap=desc[op.source]
        if isinstance(op,SortOp):
            lines += [f'  store i64 0, ptr {count}', f'  br label %copy{i}', f'copy{i}:',
                      f'  %copy_i{i} = phi i64 [ 0, %pipeline{ i-1 if i>1 else 0 } ], [ %copy_next{i}, %copy_body{i} ]',
                      f'  %copy_cond{i} = icmp ult i64 %copy_i{i}, {srccount if srccount.isdigit() else f"load i64, ptr {srccount}"}']
            # LLVM does not permit load as an operand; split dynamic count.
            lines=lines[:-1]
            if srccount.isdigit(): lines.append(f'  %copy_cond{i} = icmp ult i64 %copy_i{i}, {srccount}')
            else: lines += [f'  %copy_n{i} = load i64, ptr {srccount}', f'  %copy_cond{i} = icmp ult i64 %copy_i{i}, %copy_n{i}']
            lines += [f'  br i1 %copy_cond{i}, label %copy_body{i}, label %sort_outer_init{i}', f'copy_body{i}:',
                      f'  %copy_base{i} = {srcptr}', f'  %copy_src{i} = getelementptr double, ptr %copy_base{i}, i64 %copy_i{i}', f'  %copy_v{i} = load double, ptr %copy_src{i}',
                      f'  %copy_dst{i} = getelementptr [{cap} x double], ptr {buf}, i64 0, i64 %copy_i{i}', f'  store double %copy_v{i}, ptr %copy_dst{i}', f'  %copy_next{i} = add i64 %copy_i{i}, 1', f'  br label %copy{i}', f'sort_outer_init{i}:']
            n_expr=srccount
            if not srccount.isdigit(): lines.append(f'  %sort_n{i} = load i64, ptr {srccount}'); n_expr=f'%sort_n{i}'
            lines += [f'  br label %sort_outer{i}', f'sort_outer{i}:', f'  %outer_i{i} = phi i64 [ 0, %sort_outer_init{i} ], [ %outer_next{i}, %sort_outer_advance{i} ]',
                      f'  %outer_limit{i} = sub i64 {n_expr}, 1', f'  %outer_cond{i} = icmp ult i64 %outer_i{i}, %outer_limit{i}', f'  br i1 %outer_cond{i}, label %sort_inner_init{i}, label %sort_done{i}',
                      f'sort_inner_init{i}:', f'  br label %sort_inner{i}', f'sort_inner{i}:', f'  %inner_j{i} = phi i64 [ 0, %sort_inner_init{i} ], [ %inner_next{i}, %sort_no_swap{i} ]',
                      f'  %inner_limit{i} = sub i64 {n_expr}, 1', f'  %inner_cond{i} = icmp ult i64 %inner_j{i}, %inner_limit{i}', f'  br i1 %inner_cond{i}, label %sort_inner_body{i}, label %sort_outer_advance{i}', f'sort_inner_body{i}:',
                      f'  %left_ptr{i} = getelementptr [{cap} x double], ptr {buf}, i64 0, i64 %inner_j{i}', f'  %right_j{i} = add i64 %inner_j{i}, 1', f'  %right_ptr{i} = getelementptr [{cap} x double], ptr {buf}, i64 0, i64 %right_j{i}',
                      f'  %left{i} = load double, ptr %left_ptr{i}', f'  %right{i} = load double, ptr %right_ptr{i}']
            cmp='ogt' if op.spec.ascending else 'olt'
            lines += [f'  %swap{i} = fcmp {cmp} double %left{i}, %right{i}', f'  br i1 %swap{i}, label %sort_do_swap{i}, label %sort_no_swap{i}', f'sort_do_swap{i}:', f'  store double %right{i}, ptr %left_ptr{i}', f'  store double %left{i}, ptr %right_ptr{i}', f'  br label %sort_no_swap{i}', f'sort_no_swap{i}:', f'  %inner_next{i} = add i64 %inner_j{i}, 1', f'  br label %sort_inner{i}', f'sort_outer_advance{i}:', f'  %outer_next{i} = add i64 %outer_i{i}, 1', f'  br label %sort_outer{i}', f'sort_done{i}:']
            if srccount.isdigit(): lines.append(f'  store i64 {srccount}, ptr {count}')
            else: lines += [f'  %sorted_count{i} = load i64, ptr {srccount}', f'  store i64 %sorted_count{i}, ptr {count}']
            desc[op.result]=(f'getelementptr [{cap} x double], ptr {buf}, i64 0, i64 0',count,cap)
            current=f'sort_done{i}'
            lines += [f'  br label %pipeline{i}', f'pipeline{i}:']
            continue
        loop=f'loop{i}'; body=f'body{i}'; done=f'done{i}'; skip=f'skip{i}'
        lines += [f'  store i64 0, ptr {count}', f'  br label %{loop}', f'{loop}:', f'  %i{i} = phi i64 [ 0, %pipeline{ i-1 if i>1 else 0} ], [ %next{i}, %{skip} ]']
        if srccount.isdigit(): lines.append(f'  %src_count{i} = add i64 0, {srccount}')
        else: lines.append(f'  %src_count{i} = load i64, ptr {srccount}')
        lines += [f'  %cond{i} = icmp ult i64 %i{i}, %src_count{i}', f'  br i1 %cond{i}, label %{body}, label %{done}', f'{body}:', f'  %base{i} = {srcptr}', f'  %srcptr{i} = getelementptr double, ptr %base{i}, i64 %i{i}', f'  %value{i} = load double, ptr %srcptr{i}']
        # The pipeline backend represents each stage as one numeric scalar.
        # Preserve the semantic row-field name for the current scalar so
        # expressions such as keep(row.value) and double(row.value) remain
        # valid after a filter stage.
        stage_field = source_fields.get(op.source)
        field_values = {stage_field: f"%value{i}"} if stage_field else {}
        if isinstance(op,FilterOp):
            keep=_llvm_collection_predicate(op.predicate.expr,lines,i,signatures,field_values)
            lines += [f'  br i1 {keep}, label %keepblock{i}, label %{skip}', f'keepblock{i}:', f'  %oc{i} = load i64, ptr {count}', f'  %dst{i} = getelementptr [{cap} x double], ptr {buf}, i64 0, i64 %oc{i}', f'  store double %value{i}, ptr %dst{i}', f'  %on{i} = add i64 %oc{i}, 1', f'  store i64 %on{i}, ptr {count}', f'  br label %{skip}']
        else:
            expr=_llvm_scalar_expr(op.expr,srcptr,lines,i,signatures,field_values)
            lines += [f'  %dst{i} = getelementptr [{cap} x double], ptr {buf}, i64 0, i64 %i{i}', f'  store double {expr}, ptr %dst{i}', f'  br label %{skip}']
        lines += [f'{skip}:', f'  %next{i} = add i64 %i{i}, 1', f'  br label %{loop}', f'{done}:']
        if isinstance(op,MapOp):
            if srccount.isdigit(): lines.append(f'  store i64 {srccount}, ptr {count}')
            else: lines += [f'  %map_count{i} = load i64, ptr {srccount}', f'  store i64 %map_count{i}, ptr {count}']
        desc[op.result]=(f'getelementptr [{cap} x double], ptr {buf}, i64 0, i64 0',count,cap)
        current=f'done{i}'
        # Ensure the next stage label matches its predecessor.
        lines.append(f'  br label %pipeline{i}')
        lines.append(f'pipeline{i}:')

    srcptr,srccount,cap=desc[red.source]
    opcode={'+':0,'-':1,'*':2,'/':3}[red.expr.op]
    lines += [f'  %reduce_ptr = {srcptr}', f'  %result = call double @slang_reduce_f64(ptr %reduce_ptr, i64 {srccount if srccount.isdigit() else f"load i64, ptr {srccount}"}, double {float(red.initial.value):.17e}, i32 {opcode})']
    # Split dynamic count load into valid LLVM instructions.
    last=lines[-1]
    lines=lines[:-1]
    if srccount.isdigit(): lines.append(f'  %result = call double @slang_reduce_f64(ptr %reduce_ptr, i64 {srccount}, double {float(red.initial.value):.17e}, i32 {opcode})')
    else:
        lines += [f'  %reduce_count = load i64, ptr {srccount}', f'  %result = call double @slang_reduce_f64(ptr %reduce_ptr, i64 %reduce_count, double {float(red.initial.value):.17e}, i32 {opcode})']
    lines += ['  call i32 (ptr, ...) @printf(ptr @fmt, double %result)', '  ret i32 0', '}']
    return '\n'.join(lines)

def sort_reduce_llvm_ir(p:Program):
    """Lower a numeric data -> stable sort -> reduce pipeline to LLVM.

    This deliberately starts with the direct-data subset.  Filter/map stages
    before a sort remain handled by the broader collection aggregate backend;
    unsupported combinations fail explicitly rather than changing semantics.
    """
    validate(p)
    if len(p.ast.sorts) != 1 or len(p.ast.reduces) != 1:
        raise ValueError("native sort-reduce backend requires exactly one sort and one reduce")
    if p.ast.filters or p.ast.maps or p.ast.aggregates or p.bodies or p.simulation:
        raise ValueError("native sort-reduce backend currently accepts direct data -> sort -> reduce")
    sort = p.ast.sorts[0]
    red = p.ast.reduces[0]
    if red.source != sort.result:
        raise ValueError("native sort-reduce backend requires the reduce to consume the sorted collection")
    tables = p.data_tables or {}
    rows = tables.get(sort.source)
    if rows is None:
        raise ValueError(f"unknown sort source '{sort.source}'")
    if not isinstance(red.initial, Literal) or not isinstance(red.initial.value, (int, float)):
        raise ValueError("native sort-reduce requires a numeric literal initial accumulator")
    if not isinstance(red.expr, Binary) or not isinstance(red.expr.left, Name) or red.expr.left.name != "acc" or red.expr.op not in {"+", "-", "*", "/", "^"}:
        raise ValueError("native sort-reduce supports only 'acc <+|-|*|/> value'")
    rhs = red.expr.right
    if isinstance(rhs, Name) and rhs.name == "item":
        rhs_field = "value"
    elif isinstance(rhs, (Field, Property)) and isinstance(rhs.base, Name) and rhs.base.name == "row":
        rhs_field = rhs.name
    else:
        raise ValueError("native sort-reduce requires item or one numeric row field")
    if isinstance(sort.spec.expr, (Field, Property)) and isinstance(sort.spec.expr.base, Name) and sort.spec.expr.base.name == "row":
        sort_field = sort.spec.expr.name
    elif isinstance(sort.spec.expr, Name) and sort.spec.expr.name == "item":
        sort_field = rhs_field
    else:
        raise ValueError("native sort-reduce requires sort by item or one numeric row field")
    if sort_field != rhs_field:
        raise ValueError("native sort-reduce currently requires sort and reduce to use the same numeric field")
    values=[]
    for row in rows:
        value=row.get(rhs_field)
        if not isinstance(value,(int,float)):
            raise ValueError(f"native sort-reduce field '{rhs_field}' must be numeric")
        values.append(float(value))
    n=len(values)
    cap=max(n,1)
    elems=', '.join(f'double {v:.17e}' for v in values) or 'double 0.0'
    lines=["; ModuleID = 'slang-sort-reduce'", 'source_filename = "slang"', '', f'@data = private constant [{cap} x double] [{elems}]', '', 'declare double @slang_reduce_f64(ptr, i64, double, i32)', 'declare i32 @printf(ptr, ...)', '@fmt = private constant [7 x i8] c"%.15g\\0A\\00"', '', 'define i32 @main() {', 'entry:', f'  %buf = alloca [{cap} x double]', f'  %src = getelementptr inbounds [{cap} x double], ptr @data, i64 0, i64 0', '  br label %copy', 'copy:', '  %i = phi i64 [ 0, %entry ], [ %next, %copy_body ]', f'  %copy_cond = icmp ult i64 %i, {n}', '  br i1 %copy_cond, label %copy_body, label %outer_init', 'copy_body:', '  %sp = getelementptr double, ptr %src, i64 %i', '  %sv = load double, ptr %sp', f'  %dp = getelementptr [{cap} x double], ptr %buf, i64 0, i64 %i', '  store double %sv, ptr %dp', '  %next = add i64 %i, 1', '  br label %copy', 'outer_init:', '  br label %outer', 'outer:', '  %oi = phi i64 [ 0, %outer_init ], [ %onext, %outer_advance ]', f'  %limit = sub i64 {n}, 1', '  %ocond = icmp ult i64 %oi, %limit', '  br i1 %ocond, label %inner_init, label %reduce', 'inner_init:', '  br label %inner', 'inner:', '  %j = phi i64 [ 0, %inner_init ], [ %jnext, %no_swap ]', f'  %jlimit = sub i64 {n}, 1', '  %jcond = icmp ult i64 %j, %jlimit', '  br i1 %jcond, label %inner_body, label %outer_advance', 'inner_body:', f'  %leftp = getelementptr [{cap} x double], ptr %buf, i64 0, i64 %j', '  %rj = add i64 %j, 1', f'  %rightp = getelementptr [{cap} x double], ptr %buf, i64 0, i64 %rj', '  %left = load double, ptr %leftp', '  %right = load double, ptr %rightp']
    cmp='ogt' if sort.spec.ascending else 'olt'
    opcode={'+':0,'-':1,'*':2,'/':3}[red.expr.op]
    lines += [f'  %swap = fcmp {cmp} double %left, %right', '  br i1 %swap, label %do_swap, label %no_swap', 'do_swap:', '  store double %right, ptr %leftp', '  store double %left, ptr %rightp', '  br label %no_swap', 'no_swap:', '  %jnext = add i64 %j, 1', '  br label %inner', 'outer_advance:', '  %onext = add i64 %oi, 1', '  br label %outer', 'reduce:', f'  %sorted = getelementptr [{cap} x double], ptr %buf, i64 0, i64 0', f'  %result = call double @slang_reduce_f64(ptr %sorted, i64 {n}, double {float(red.initial.value):.17e}, i32 {opcode})', '  call i32 (ptr, ...) @printf(ptr @fmt, double %result)', '  ret i32 0', '}']
    return '\n'.join(lines)

def _selected_native_strategy(p:Program) -> str:
    """Return the strategy selected by the canonical semantic planning pipeline."""
    from .compiler_pipeline import compile_semantic_pipeline
    from .backend import native_capabilities
    result = compile_semantic_pipeline(p.ast, native_capabilities().supported_strategies)
    choices = {choice.node: choice.strategy for choice in result.strategies}
    terminal = None
    if p.ast.reduces:
        terminal = p.ast.reduces[0].result
    elif p.ast.aggregates:
        terminal = p.ast.aggregates[0].result
    elif p.ast.sorts:
        terminal = p.ast.sorts[0].result
    if terminal is None:
        if p.ast.filters:
            terminal = p.ast.filters[-1].result
        elif p.ast.maps:
            terminal = p.ast.maps[-1].result
    if terminal is None:
        return "generic"
    return choices.get(terminal + "#1", choices.get(terminal, "generic"))



def _llvm_c_string(value: str) -> tuple[str, int]:
    """Return an LLVM-safe byte string and its null-terminated length."""
    raw = value.encode("utf-8") + b"\x00"
    encoded = "".join(f"\\{b:02X}" if b < 32 or b >= 127 or b in (34, 92) else chr(b) for b in raw)
    return encoded, len(raw)


def _native_system_call_expr(expr, env, globals_out, declarations, user_signatures=None):
    """Lower a small scalar/system subset to LLVM.

    The native system layer uses explicit C ownership for text and text-list
    results. Returned buffers/lists are released by the generated executable
    after their last use.
    """
    if isinstance(expr, Literal) and isinstance(expr.value, list):
        if not all(isinstance(item, Literal) and isinstance(item.value, str) for item in expr.value):
            raise ValueError("native text-list literals require only Text elements")
        tmp = f"%sys_list_{len(env)}_{len(declarations)}"
        declarations.append(f"  {tmp} = call ptr @slang_text_list_new(i64 {len(expr.value)})")
        for i, item in enumerate(expr.value):
            _, ptr_value = _native_system_call_expr(item, env, globals_out, declarations)
            declarations.append(f"  %sys_list_set_{len(env)}_{len(declarations)} = call i1 @slang_text_list_set(ptr {tmp}, i64 {i}, ptr {ptr_value})")
        return "text_list", tmp
    if isinstance(expr, Literal):
        if isinstance(expr.value, bool):
            return "i1", "1" if expr.value else "0"
        if isinstance(expr.value, (int, float)) and not isinstance(expr.value, bool):
            return "double", f"{float(expr.value):.17e}"
        if isinstance(expr.value, str):
            key = f"str_{len(globals_out)}"
            encoded, length = _llvm_c_string(expr.value)
            globals_out.append((key, encoded, length))
            return "ptr", f"getelementptr inbounds ([{length} x i8], ptr @{key}, i64 0, i64 0)"
        raise ValueError("native scalar backend supports only Number, Boolean, and Text literals")
    if isinstance(expr, Name):
        if expr.name not in env:
            raise ValueError(f"native scalar backend cannot resolve binding '{expr.name}'")
        return env[expr.name]
    if isinstance(expr, Conditional):
        ctyp, cv = _native_system_call_expr(expr.condition, env, globals_out, declarations, user_signatures)
        if ctyp != "i1":
            raise ValueError("native conditional expression condition must be Boolean")
        ttyp, tv = _native_system_call_expr(expr.then_expr, env, globals_out, declarations, user_signatures)
        etyp, ev = _native_system_call_expr(expr.else_expr, env, globals_out, declarations, user_signatures)
        if ttyp != etyp or ttyp not in {"double", "i1"}:
            raise ValueError("native conditional expression requires matching Number or Boolean branches")
        tmp = f"%sys_select_{len(env)}_{len(declarations)}"
        declarations.append(f"  {tmp} = select i1 {cv}, {ttyp} {tv}, {etyp} {ev}")
        return ttyp, tmp
    if isinstance(expr, Binary) and expr.op in {"+", "-", "*", "/"}:
        lt, lv = _native_system_call_expr(expr.left, env, globals_out, declarations, user_signatures)
        rt, rv = _native_system_call_expr(expr.right, env, globals_out, declarations, user_signatures)
        if lt != "double" or rt != "double":
            raise ValueError("native scalar arithmetic requires Number operands")
        op = {"+": "fadd", "-": "fsub", "*": "fmul", "/": "fdiv", "%": "frem"}[expr.op]
        tmp = f"%sys_expr_{len(env)}_{len(declarations)}"
        declarations.append(f"  {tmp} = {op} double {lv}, {rv}")
        return "double", tmp
    if isinstance(expr, Compare) and expr.op in {">", ">=", "<", "<=", "==", "!="}:
        lt, lv = _native_system_call_expr(expr.left, env, globals_out, declarations, user_signatures)
        rt, rv = _native_system_call_expr(expr.right, env, globals_out, declarations, user_signatures)
        if lt != "double" or rt != "double":
            raise ValueError("native scalar comparisons require Number operands")
        pred = {">": "ogt", ">=": "oge", "<": "olt", "<=": "ole", "==": "oeq", "!=": "one"}[expr.op]
        tmp = f"%sys_cmp_{len(env)}_{len(declarations)}"
        declarations.append(f"  {tmp} = fcmp {pred} double {lv}, {rv}")
        return "i1", tmp
    if isinstance(expr, Logical):
        if expr.op == "not":
            typ, value = _native_system_call_expr(expr.left, env, globals_out, declarations, user_signatures)
            if typ != "i1": raise ValueError("native logical operators require Boolean operands")
            tmp = f"%sys_not_{len(env)}_{len(declarations)}"
            declarations.append(f"  {tmp} = xor i1 {value}, true")
            return "i1", tmp
        lt, lv = _native_system_call_expr(expr.left, env, globals_out, declarations, user_signatures)
        rt, rv = _native_system_call_expr(expr.right, env, globals_out, declarations, user_signatures)
        if lt != "i1" or rt != "i1":
            raise ValueError("native logical operators require Boolean operands")
        op = "and" if expr.op == "and" else "or"
        tmp = f"%sys_logic_{len(env)}_{len(declarations)}"
        declarations.append(f"  {tmp} = {op} i1 {lv}, {rv}")
        return "i1", tmp
    if isinstance(expr, Call):
        if user_signatures and expr.name in user_signatures:
            params, result_type = user_signatures[expr.name]
            if len(expr.args) != len(params):
                raise ValueError(f"native function '{expr.name}' expects {len(params)} argument(s)")
            args=[]
            for arg, expected in zip(expr.args, params):
                typ, value = _native_system_call_expr(arg, env, globals_out, declarations, user_signatures)
                if typ != expected:
                    raise ValueError(f"native function '{expr.name}' argument type mismatch")
                args.append(f"{typ} {value}")
            tmp=f"%sys_fn_call_{len(env)}_{len(declarations)}"
            declarations.append(f"  {tmp} = call {result_type} @{expr.name}({', '.join(args)})")
            return result_type, tmp
        names = {"exists": ("slang_file_exists", "i1", ("ptr",), "i1"),
                 "file_size": ("slang_file_size", "double", ("ptr",), "double"),
                 "is_file": ("slang_is_file", "i1", ("ptr",), "i1"),
                 "is_directory": ("slang_is_directory", "i1", ("ptr",), "i1"),
                 "write": ("slang_file_write", "i1", ("ptr", "ptr"), "i1"),
                 "read": ("slang_file_read", "ptr", ("ptr",), "text"),
                 "read_lines": ("slang_file_read_lines", "ptr", ("ptr",), "text_list"),
                 "list_directory": ("slang_file_list_directory", "ptr", ("ptr",), "text_list"),
                 "make_directory": ("slang_make_directory", "i1", ("ptr",), "i1"),
                 "remove_directory": ("slang_remove_directory", "i1", ("ptr",), "i1"),
                 "write_lines": ("slang_file_write_lines", "i1", ("ptr", "text_list"), "i1"),
                 "basename": ("slang_path_basename", "ptr", ("ptr",), "text"),
                 "dirname": ("slang_path_dirname", "ptr", ("ptr",), "text"),
                 "extension": ("slang_path_extension", "ptr", ("ptr",), "text"),
                 "join_path": ("slang_path_join", "ptr", ("ptr", "ptr"), "text"),
                 "normalize_path": ("slang_path_normalize", "ptr", ("ptr",), "text"),
                 "arguments": ("slang_process_arguments", "ptr", (), "text_list"),
                 "environment": ("slang_process_environment", "ptr", ("ptr",), "text"),
                 "run_process": ("slang_process_run", "ptr", ("ptr",), "text_list"),
                 "run_program": ("slang_process_run_program", "ptr", ("ptr", "text_list", "ptr"), "text_list"),
                 "run_program_with_environment": ("slang_process_run_program_env", "ptr", ("ptr", "text_list", "ptr", "text_list"), "text_list"),
                 "trim": ("slang_text_trim", "ptr", ("ptr",), "text"),
                 "lower": ("slang_text_lower", "ptr", ("ptr",), "text"),
                 "upper": ("slang_text_upper", "ptr", ("ptr",), "text"),
                 "starts_with": ("slang_text_starts_with", "i1", ("ptr", "ptr"), "i1"),
                 "ends_with": ("slang_text_ends_with", "i1", ("ptr", "ptr"), "i1"),
                 "replace": ("slang_text_replace", "ptr", ("ptr", "ptr", "ptr"), "text"),
                 "split": ("slang_text_split", "ptr", ("ptr", "ptr"), "text_list")}
        if expr.name not in names:
            raise ValueError(f"native scalar backend does not support call '{expr.name}'")
        function, result_type, arg_types, semantic_kind = names[expr.name]
        if len(expr.args) != len(arg_types):
            raise ValueError(f"native call '{expr.name}' expects {len(arg_types)} argument(s)")
        args=[]
        for arg, expected in zip(expr.args, arg_types):
            typ, value = _native_system_call_expr(arg, env, globals_out, declarations, user_signatures)
            compatible = (typ == expected) or (expected == "ptr" and typ == "text") or (expected == "text" and typ == "ptr")
            if not compatible:
                raise ValueError(f"native call '{expr.name}' requires {expected} argument(s)")
            abi_typ = "ptr" if expected in {"text_list", "text", "ptr"} else typ
            args.append(f"{abi_typ} {value}")
        if function == "slang_process_arguments":
            if function not in declarations:
                declarations.insert(0, "declare ptr @slang_process_arguments(i32, ptr)")
            call_args = "i32 %argc, ptr %argv"
        else:
            if function not in declarations:
                declarations.insert(0, f"declare {result_type} @{function}({', '.join('ptr' if t == 'text_list' else t for t in arg_types)})")
            call_args = ', '.join(args)
        tmp = f"%sys_call_{len(env)}_{len(declarations)}"
        declarations.append(f"  {tmp} = call {result_type} @{function}({call_args})")
        for arg_index, (arg, expected) in enumerate(zip(expr.args, arg_types)):
            if expected == "text_list" and isinstance(arg, Literal) and isinstance(arg.value, list):
                declarations.append(f"  call void @slang_text_list_free(ptr {args[arg_index].split(' ', 1)[1]})")
        return semantic_kind, tmp
    raise ValueError(f"native scalar backend does not support expression {type(expr).__name__}")


def _native_system_calls_in_expr(expr):
    if isinstance(expr, Call):
        out={expr.name}
        for arg in expr.args: out |= _native_system_calls_in_expr(arg)
        return out
    if isinstance(expr, (Binary, Compare, Logical)):
        return _native_system_calls_in_expr(expr.left) | (_native_system_calls_in_expr(expr.right) if getattr(expr, "right", None) is not None else set())
    return set()




def _nested_record_constructor_collection_llvm_ir(p: Program, records: dict[str, object]):
    """Lower List<Record> map stages that construct nested records."""
    validate(p)
    def path_of(expr):
        parts=[]; cur=expr
        while isinstance(cur, Property):
            parts.append(cur.name); cur=cur.base
        if isinstance(cur, Name) and cur.name in {"row","item"} and parts:
            return tuple(reversed(parts))
        return None
    sources={}
    for b in p.ast.bindings:
        v=b.expr
        if isinstance(v, Literal) and isinstance(v.value,list) and v.value and all(isinstance(x,Call) and x.name in records for x in v.value):
            rn=v.value[0].name
            if all(x.name==rn for x in v.value): sources[b.name]=(rn,v.value)
    if not sources: raise ValueError("native nested record map requires a literal record-list source")
    rname, rows=next(iter(sources.values()))
    def field_decl(rn,name):
        for i,(fname,t) in enumerate(records[rn].fields):
            if fname==name: return i,t.name
        raise ValueError(f"unknown record field '{rn}.{name}'")
    def resolve(rn,path):
        cur=rn
        for i,part in enumerate(path):
            _,typ=field_decl(cur,part)
            if i==len(path)-1: return typ
            if typ not in records: raise ValueError(f"field '{cur}.{part}' is not a record")
            cur=typ
    def leaf_paths(rn,prefix=()):
        out=[]
        for fname,typ in records[rn].fields:
            q=prefix+(fname,)
            if typ.name in records: out.extend(leaf_paths(typ.name,q))
            else: out.append(q)
        return out
    def value_at_call(call,path,root_type):
        cur=call; curtype=root_type
        for i,part in enumerate(path):
            idx,typ=field_decl(curtype,part); arg=cur.args[idx]
            if i==len(path)-1: return arg
            if not isinstance(arg,Call) or arg.name not in records: raise ValueError("nested record constructor requires nested record values")
            cur=arg; curtype=typ
    def constructor_expr(call,path):
        cur=call; curtype=call.name
        for i,part in enumerate(path):
            idx,typ=field_decl(curtype,part); cur=cur.args[idx]
            if i<len(path)-1:
                if not isinstance(cur,Call) or cur.name not in records: raise ValueError("nested record constructor shape mismatch")
                curtype=cur.name
        return cur
    leaves=leaf_paths(rname)
    lines=["; ModuleID = 'slang-nested-record-map'",'source_filename = "slang"','']
    data={}
    def emit_source_array(name,vals,typ):
        if typ=='Number':
            if not all(isinstance(v,Literal) and isinstance(v.value,(int,float)) and not isinstance(v.value,bool) for v in vals): raise ValueError("native nested numeric leaves must be literals")
            lines.append(f"@nrm_{name} = private constant [{len(vals)} x double] [{', '.join('double '+format(float(v.value),'.17e') for v in vals)}]")
        elif typ=='Boolean':
            if not all(isinstance(v,Literal) and isinstance(v.value,bool) for v in vals): raise ValueError("native nested Boolean leaves must be literals")
            lines.append(f"@nrm_{name} = private constant [{len(vals)} x i1] [{', '.join('i1 1' if v.value else 'i1 0' for v in vals)}]")
        elif typ=='Text':
            ptrs=[]
            for j,v in enumerate(vals):
                if not isinstance(v,Literal) or not isinstance(v.value,str): raise ValueError("native nested text leaves must be literals")
                enc,l=_llvm_c_string(v.value); nm=f"@nrm_src_{name}_{j}"; lines.append(f' {nm} = private constant [{l} x i8] c"{enc}"'); ptrs.append(f"ptr getelementptr inbounds ([{l} x i8], ptr {nm}, i64 0, i64 0)")
            lines.append(f"@nrm_{name} = private constant [{len(vals)} x ptr] [{', '.join(ptrs)}]")
        else: raise ValueError(f"unsupported nested leaf type '{typ}'")
        return f"@nrm_{name}",len(vals),typ
    for q in leaves:
        data[q]=emit_source_array('_'.join(q),[value_at_call(x,q,rname) for x in rows],resolve(rname,q))
    lines += ['', 'declare i32 @printf(ptr, ...)', '@nrm_num_fmt = private constant [7 x i8] c"%.15g\\0A\\00"', '@nrm_bool_t = private constant [5 x i8] c"true\\00"', '@nrm_bool_f = private constant [6 x i8] c"false\\00"', '@nrm_bool_fmt = private constant [4 x i8] c"%s\\0A\\00"', '@nrm_text_fmt = private constant [4 x i8] c"%s\\0A\\00"', 'define i32 @main() {', 'entry:']
    current='entry'; desc={}; serial=0
    def load_path(q,idx,tag):
        nonlocal serial
        g,n,t=data[q]; llvm={'Number':'double','Boolean':'i1','Text':'ptr'}[t]; serial+=1
        pv=f"%nrm_p_{tag}_{serial}"; vv=f"%nrm_v_{tag}_{serial}"; lines.append(f"  {pv} = getelementptr inbounds [{n} x {llvm}], ptr {g}, i64 0, i64 {idx}"); lines.append(f"  {vv} = load {llvm}, ptr {pv}"); return t,vv
    def expr_value(expr,idx,tag,expected=None,source_data=None):
        q=path_of(expr)
        if q:
            if q not in source_data: raise ValueError(f"unknown nested record path '{'.'.join(q)}'")
            g,n,t=source_data[q]; llvm={'Number':'double','Boolean':'i1','Text':'ptr'}[t]; serial_tag=f"{tag}_{len(lines)}"; pv=f"%nrm_p_{serial_tag}"; vv=f"%nrm_v_{serial_tag}"; lines.append(f"  {pv} = getelementptr inbounds [{n} x {llvm}], ptr {g}, i64 0, i64 {idx}"); lines.append(f"  {vv} = load {llvm}, ptr {pv}");
            if expected and t!=expected: raise ValueError(f"nested record field requires {expected}")
            return t,vv
        if isinstance(expr,Literal):
            if isinstance(expr.value,bool): typ='Boolean'; val='1' if expr.value else '0'
            elif isinstance(expr.value,(int,float)) and not isinstance(expr.value,bool): typ='Number'; val=format(float(expr.value),'.17e')
            elif isinstance(expr.value,str):
                typ='Text'; enc,l=_llvm_c_string(expr.value); nm=f"@nrm_expr_{tag}_{len(lines)}"; lines.append(f' {nm} = private constant [{l} x i8] c"{enc}"'); val=f"getelementptr inbounds ([{l} x i8], ptr {nm}, i64 0, i64 0)"
            else: raise ValueError("unsupported nested record literal")
            if expected and typ!=expected: raise ValueError(f"nested record field requires {expected}")
            return typ,val
        if isinstance(expr,Binary) and expr.op in {'+','-','*','/'}:
            a,av=expr_value(expr.left,idx,tag,'Number',source_data); b,bv=expr_value(expr.right,idx,tag,'Number',source_data); op={'+' :'fadd','-':'fsub','*':'fmul','/':'fdiv'}[expr.op]; n=f"%nrm_e_{tag}_{len(lines)}"; lines.append(f"  {n} = {op} double {av}, {bv}"); return 'Number',n
        raise ValueError("native nested record map expression is unsupported")
    for op in p.ast.maps:
        if op.source not in sources and op.source not in desc: raise ValueError("native nested record map source must be a record collection")
        if isinstance(op.expr,Call) and op.expr.name in records:
            out_rn=op.expr.name; out_leaves=leaf_paths(out_rn); cap=len(rows) if op.source in sources else desc[op.source][2]; count=str(cap) if op.source in sources else desc[op.source][1]
            srcdata=data if op.source in sources else desc[op.source][0]
            outbuf={}
            for q in out_leaves:
                typ=resolve(out_rn,q); llvm={'Number':'double','Boolean':'i1','Text':'ptr'}[typ]; buf=f"%nrm_buf_{len(desc)}_{'_'.join(q)}"; outbuf[q]=(buf,cap,typ); lines.append(f"  {buf} = alloca [{cap or 1} x {llvm}]")
            serial+=1; loop=f"nrm_l_{serial}"; body=f"nrm_b_{serial}"; done=f"nrm_d_{serial}"; maxline=f"  %nrm_m_{serial} = add i64 0, {count}" if str(count).isdigit() else f"  %nrm_m_{serial} = load i64, ptr {count}"; lines += [f"  br label %{loop}",f"{loop}:",f"  %nrm_i_{serial} = phi i64 [ 0, %{current} ], [ %nrm_n_{serial}, %{body} ]",maxline,f"  %nrm_h_{serial} = icmp ult i64 %nrm_i_{serial}, %nrm_m_{serial}",f"  br i1 %nrm_h_{serial}, label %{body}, label %{done}",f"{body}:"]
            for q in out_leaves:
                expr=constructor_expr(op.expr,q); typ=resolve(out_rn,q); et,ev=expr_value(expr,f"%nrm_i_{serial}",f"{serial}_{'_'.join(q)}",typ,srcdata); llvm={'Number':'double','Boolean':'i1','Text':'ptr'}[typ]; dp=f"%nrm_dp_{serial}_{'_'.join(q)}"; lines.append(f"  {dp} = getelementptr [{cap or 1} x {llvm}], ptr {outbuf[q][0]}, i64 0, i64 %nrm_i_{serial}"); lines.append(f"  store {llvm} {ev}, ptr {dp}")
            lines += [f"  %nrm_n_{serial} = add i64 %nrm_i_{serial}, 1",f"  br label %{loop}",f"{done}:"]; desc[op.result]=(outbuf,count,cap,'record',out_rn); current=done
        else:
            q=path_of(op.expr); src=desc.get(op.source)
            if not q or src is None: raise ValueError("native nested record map requires a record constructor or field path")
            srcdata,count,cap,kind,src_rn=src
            if q not in srcdata: raise ValueError(f"unknown nested record path '{'.'.join(q)}'")
            typ=resolve(src_rn,q); llvm={'Number':'double','Boolean':'i1','Text':'ptr'}[typ]; out=f"%nrm_proj_{len(desc)}"; lines.append(f"  {out} = alloca [{cap or 1} x {llvm}]"); serial+=1; loop=f"nrm_pl_{serial}"; body=f"nrm_pb_{serial}"; done=f"nrm_pd_{serial}"; maxline=f"  %nrm_pm_{serial} = add i64 0, {count}" if str(count).isdigit() else f"  %nrm_pm_{serial} = load i64, ptr {count}"; lines += [f"  br label %{loop}",f"{loop}:",f"  %nrm_pi_{serial} = phi i64 [ 0, %{current} ], [ %nrm_pn_{serial}, %{body} ]",maxline,f"  %nrm_ph_{serial} = icmp ult i64 %nrm_pi_{serial}, %nrm_pm_{serial}",f"  br i1 %nrm_ph_{serial}, label %{body}, label %{done}",f"{body}:"]
            g,n,t=srcdata[q]; sp=f"%nrm_sp_{serial}"; sv=f"%nrm_sv_{serial}"; dp=f"%nrm_dp_{serial}"; lines += [f"  {sp} = getelementptr [{n} x {llvm}], ptr {g}, i64 0, i64 %nrm_pi_{serial}",f"  {sv} = load {llvm}, ptr {sp}",f"  {dp} = getelementptr [{cap or 1} x {llvm}], ptr {out}, i64 0, i64 %nrm_pi_{serial}",f"  store {llvm} {sv}, ptr {dp}",f"  %nrm_pn_{serial} = add i64 %nrm_pi_{serial}, 1",f"  br label %{loop}",f"{done}:"]; desc[op.result]=(out,count,cap,typ,src_rn); current=done
    show={x.name for x in p.show_exprs if isinstance(x,Name)}
    for j,(name,d) in enumerate(desc.items()):
        if name not in show: continue
        ptr,cnt,cap,kind,*_=d
        if kind not in {'Number','Boolean','Text'}: raise ValueError("show requires a scalar nested-record projection")
        llvm={'Number':'double','Boolean':'i1','Text':'ptr'}[kind]; loop=f"nrm_sl_{j}"; body=f"nrm_sb_{j}"; done=f"nrm_sd_{j}"; lines += [f"  br label %{loop}",f"{loop}:",f"  %nrm_si_{j} = phi i64 [ 0, %{current} ], [ %nrm_sn_{j}, %{body} ]",f"  %nrm_sc_{j} = add i64 0, {cnt}" if str(cnt).isdigit() else f"  %nrm_sc_{j} = load i64, ptr {cnt}",f"  %nrm_sx_{j} = icmp ult i64 %nrm_si_{j}, %nrm_sc_{j}",f"  br i1 %nrm_sx_{j}, label %{body}, label %{done}",f"{body}:"]
        sp=f"%nrm_showp_{j}"; sv=f"%nrm_showv_{j}"; lines += [f"  {sp} = getelementptr [{cap or 1} x {llvm}], ptr {ptr}, i64 0, i64 %nrm_si_{j}",f"  {sv} = load {llvm}, ptr {sp}"]
        if kind=='Number': lines.append(f"  call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([7 x i8], ptr @nrm_num_fmt, i64 0, i64 0), double {sv})")
        elif kind=='Text': lines.append(f"  call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([4 x i8], ptr @nrm_text_fmt, i64 0, i64 0), ptr {sv})")
        else: lines.append(f"  %nrm_bp_{j} = select i1 {sv}, ptr getelementptr inbounds ([5 x i8], ptr @nrm_bool_t, i64 0, i64 0), ptr getelementptr inbounds ([6 x i8], ptr @nrm_bool_f, i64 0, i64 0)"); lines.append(f"  call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([4 x i8], ptr @nrm_bool_fmt, i64 0, i64 0), ptr %nrm_bp_{j})")
        lines += [f"  %nrm_sn_{j} = add i64 %nrm_si_{j}, 1",f"  br label %{loop}",f"{done}:"]; current=done
    lines += ['  ret i32 0','}','']
    return '\n'.join(lines)
def record_collection_sort_llvm_ir(p: Program):
    """Lower a record collection through filters, stable sorts and terminals.

    Reassigned collection names are normalized to internal SSA-like stage
    names before graph traversal. This preserves source order for pipelines
    such as ``map -> filter -> map`` where the same public variable is reused.
    """
    validate(p)
    # The AST stores filters, maps and sorts in separate lists. Resolve them
    # in source order and version each result so rebinding does not create
    # ambiguous sibling stages with the same public source name.
    raw_stages = list(p.ast.filters) + list(p.ast.maps) + list(p.ast.sorts)
    raw_stages.sort(key=lambda op: (
        source_span_of(op).start.line if source_span_of(op) else 10**9,
        source_span_of(op).start.column if source_span_of(op) else 10**9,
    ))
    latest = {}
    normalized = {FilterOp: [], MapOp: [], SortOp: []}
    for index, op in enumerate(raw_stages, 1):
        source = latest.get(op.source, op.source)
        result = f"__slang_record_stage_{index}"
        updated = replace(op, source=source, result=result)
        updated = mark_source_span(updated, source_span_of(op))
        normalized[type(op)].append(updated)
        latest[op.result] = result
    p.ast.filters = normalized[FilterOp]
    p.ast.maps = normalized[MapOp]
    p.ast.sorts = normalized[SortOp]
    p.ast.aggregates = [replace(item, source=latest.get(item.source, item.source)) for item in p.ast.aggregates]
    p.ast.reduces = [replace(item, source=latest.get(item.source, item.source)) for item in p.ast.reduces]
    if p.bodies or p.simulation:
        raise ValueError("native record sort backend accepts filter/sort/map/reduce/aggregate programs")
    if p.ast.aggregates and p.ast.reduces:
        raise ValueError("native record sort backend supports one terminal reduce or aggregate, not both")
    if len(p.ast.reduces) > 1:
        raise ValueError("native record sort backend supports at most one reduce operation")
    if not p.ast.sorts:
        raise ValueError("native record sort backend requires at least one sort operation")
    records = {r.name: r for r in p.ast.records}
    sources = {}
    for b in p.ast.bindings:
        v=b.expr
        if not (isinstance(v, Literal) and isinstance(v.value, list) and v.value):
            continue
        xs=v.value
        if not all(isinstance(x, Call) and x.name in records for x in xs):
            continue
        rn=xs[0].name
        if any(x.name != rn for x in xs):
            continue
        sources[b.name]=(rn,xs)
    if not sources:
        raise ValueError("native record sort requires a record-list literal source")

    # Start from the final sort and walk the collection graph backwards.
    # Reassignments may reuse the same result name (for example
    # `ordered = ordered sort ...`), so sort stages must be resolved by their
    # source order rather than stored in a result-name dictionary.
    sort = p.ast.sorts[-1]
    by_result = {op.result: op for op in list(p.ast.filters)+list(p.ast.maps)}
    chain=[sort]
    source = sort.source
    preceding_sort_index=len(p.ast.sorts)-2
    while True:
        previous_sort=None
        while preceding_sort_index >= 0:
            candidate=p.ast.sorts[preceding_sort_index]
            preceding_sort_index-=1
            if candidate.result == source:
                previous_sort=candidate
                break
        if previous_sort is not None:
            chain.insert(0, previous_sort)
            source=previous_sort.source
            continue
        if source not in by_result:
            break
        op=by_result[source]
        chain.insert(0, op)
        source=op.source
    if source not in sources:
        raise ValueError("native record sort requires a literal record-list source")
    rn, rows = sources[source]
    decl=records[rn]

    # Flatten nested record leaves into parallel scalar buffers. The internal
    # key uses `__` so it is safe in LLVM identifiers while field paths in the
    # source remain dotted (for example `row.address.code`).
    fields={}
    def add_leaf_types(record_name, prefix="", active=()):
        if record_name in active:
            raise ValueError("native record sort does not support recursive record types")
        record_decl=records.get(record_name)
        if record_decl is None:
            raise ValueError(f"unknown nested record type '{record_name}'")
        for field_name, field_type in record_decl.fields:
            key=f"{prefix}__{field_name}" if prefix else field_name
            if field_type.name in {"Number", "Boolean", "Text"}:
                fields[key]=field_type
            elif field_type.name in records:
                add_leaf_types(field_type.name, key, active+(record_name,))
            else:
                raise ValueError(f"native record sort does not support field type '{field_type.name}'")
    add_leaf_types(rn)

    def record_leaf_values(record_expr, record_name, prefix="", active=()):
        if record_name in active:
            raise ValueError("native record sort does not support recursive record values")
        if not isinstance(record_expr, Call) or record_expr.name != record_name:
            raise ValueError(f"native record sort requires literal '{record_name}' record values")
        record_decl=records[record_name]
        if len(record_expr.args) != len(record_decl.fields):
            raise ValueError(f"native record sort record '{record_name}' constructor arity mismatch")
        out={}
        for (field_name, field_type), arg in zip(record_decl.fields, record_expr.args):
            key=f"{prefix}__{field_name}" if prefix else field_name
            if field_type.name in {"Number", "Boolean", "Text"}:
                if not isinstance(arg, Literal):
                    raise ValueError(f"native record sort requires literal scalar field '{key}'")
                out[key]=arg.value
            elif field_type.name in records:
                out.update(record_leaf_values(arg, field_type.name, key, active+(record_name,)))
            else:
                raise ValueError(f"native record sort does not support field type '{field_type.name}'")
        return out

    # The pipeline may filter records before sorting and may project one scalar
    # field after sorting. Since 1.8.71, a map before sort is also allowed when
    # it preserves the same Record type. This is important for the common
    # pattern `map Record -> Record -> sort -> map field`.
    post_maps=[]
    pre_maps=[m for m in chain if isinstance(m,MapOp)]
    sort_seen=False
    for op in chain:
        if isinstance(op, SortOp):
            sort_seen=True
        elif isinstance(op, MapOp):
            # Record-preserving maps are lowered below; scalar maps before sort
            # would destroy the record shape and remain unsupported.
            if not (isinstance(op.expr, Call) and op.expr.name in records):
                if not (isinstance(op.expr, Call) and any(fn.name == op.expr.name for fn in p.ast.functions)):
                    raise ValueError("native record sort does not support scalar map before sort")
    if not sort_seen:
        raise ValueError("native record sort pipeline requires a sort stage")
    # Collect every record-preserving stage after the sort, including filters.
    # The earlier implementation collected only maps, which made a `where`
    # after `sort` invisible to native lowering.
    post_chain=[]
    cursor=sort.result
    while True:
        candidates=[op for op in (list(p.ast.filters)+list(p.ast.maps)) if op.source == cursor]
        if not candidates:
            break
        if len(candidates) > 1:
            raise ValueError("native record sort requires a linear post-sort pipeline")
        nxt=candidates[0]
        post_chain.append(nxt)
        cursor=nxt.result
    chain.extend(post_chain)
    post_maps=[m for m in post_chain if isinstance(m,MapOp)]

    # 1.8.71: inline the currently supported pure Record -> Record function
    # shape into its returned Record constructor. This keeps the native sort
    # backend deterministic and avoids giving functions a second collection
    # representation. Only a function whose native return is a same-type Record
    # constructor is accepted.
    fn_by_name={fn.name: fn for fn in p.ast.functions}
    def inline_record_function(expr):
        if not isinstance(expr, Call) or expr.name not in fn_by_name:
            return expr
        fn=fn_by_name[expr.name]
        if len(fn.parameters) != len(expr.args):
            raise ValueError(f"native record sort function '{fn.name}' argument count mismatch")
        ret=next((st for st in fn.body if isinstance(st, ReturnOp)), None)
        if ret is None or not isinstance(ret.expr, Call) or ret.expr.name not in records:
            raise ValueError(f"native record sort function '{fn.name}' must return a Record constructor")
        mapping={pname:arg for (pname,_),arg in zip(fn.parameters,expr.args)}
        def sub(x):
            if isinstance(x,Name) and x.name in mapping: return mapping[x.name]
            if isinstance(x,Field): return Field(sub(x.base),x.name)
            if isinstance(x,Property): return Property(sub(x.base),x.name)
            if isinstance(x,Binary): return Binary(x.op,sub(x.left),sub(x.right))
            if isinstance(x,Compare): return Compare(x.op,sub(x.left),sub(x.right))
            if isinstance(x,Logical): return Logical(x.op,sub(x.left),sub(x.right))
            if isinstance(x,Call): return Call(x.name,tuple(sub(a) for a in x.args))
            return x
        out=sub(ret.expr)
        if not isinstance(out,Call) or out.name != rn:
            raise ValueError(f"native record sort function '{fn.name}' must return the pipeline Record type")
        return out
    chain=[replace(op,expr=inline_record_function(op.expr)) if isinstance(op,MapOp) else op for op in chain]

    # 1.8.76: filters are semantically ordered with maps, but filtering is
    # independent of ordering and therefore may be lowered before the map
    # stages if its predicate is translated back through the preceding pure
    # Record -> Record maps. This preserves pipelines such as
    # `map -> where -> sort -> map -> where -> map -> aggregate` while keeping
    # the native representation compact.
    def substitute_record_expr(expr, mapping):
        if isinstance(expr, Name) and expr.name in mapping:
            return mapping[expr.name]
        if isinstance(expr, (Field, Property)):
            return type(expr)(substitute_record_expr(expr.base, mapping), expr.name)
        if isinstance(expr, (Binary, Compare, Logical)):
            if isinstance(expr, Logical):
                return Logical(expr.op, substitute_record_expr(expr.left, mapping),
                                substitute_record_expr(expr.right, mapping) if expr.right is not None else None)
            return type(expr)(expr.op, substitute_record_expr(expr.left, mapping),
                              substitute_record_expr(expr.right, mapping))
        if isinstance(expr, Call):
            return Call(expr.name, tuple(substitute_record_expr(a, mapping) for a in expr.args))
        return expr

    def record_map_mapping(op):
        if not (isinstance(op.expr, Call) and op.expr.name == rn and len(op.expr.args) == len(decl.fields)):
            return None
        return {fname: arg for (fname,_), arg in zip(decl.fields, op.expr.args)}

    sort_pos=next(i for i,o in enumerate(chain) if isinstance(o,SortOp))
    sort_positions=[i for i,o in enumerate(chain) if isinstance(o,SortOp)]
    first_sort_pos=sort_positions[0]
    last_sort_pos=sort_positions[-1]
    # Multiple sort stages are supported as stable passes when they are
    # consecutive. This is the conventional stable multi-key sorting pattern:
    # sort by the least-significant key first, then by the primary key.
    if any(not isinstance(chain[i], SortOp) for i in range(first_sort_pos, last_sort_pos + 1)):
        raise ValueError("native record sort stages must be consecutive")
    sort_ops=[chain[i] for i in sort_positions]
    pre_maps=[o for o in chain[:first_sort_pos] if isinstance(o,MapOp)]
    post_maps0=[o for o in chain[last_sort_pos+1:] if isinstance(o,MapOp)]
    filters_pre=[]
    filters_post=[]
    for oi,o in enumerate(chain):
        if isinstance(o,FilterOp):
            pred=o.predicate.expr
            preceding_maps=[m for m in chain[:oi] if isinstance(m,MapOp)]
            for mop in reversed(preceding_maps):
                mm=record_map_mapping(mop)
                if mm is None:
                    # Scalar maps expose their result as `item`/`value` to
                    # subsequent filters. Inline that pure expression so the
                    # filter can be evaluated against the sorted record rows.
                    pred=substitute_record_expr(pred, {"item": mop.expr, "value": mop.expr})
                    continue
                pred=substitute_record_expr(pred, {"row": Call(rn, tuple(mm[f] for f,_ in decl.fields))})
                def reduce_ctor(x):
                    if isinstance(x,(Field,Property)) and isinstance(x.base,Call) and x.base.name==rn:
                        idx=next((i for i,(fn,_) in enumerate(decl.fields) if fn==x.name),None)
                        if idx is not None: return x.base.args[idx]
                    if isinstance(x,(Field,Property)):
                        return type(x)(reduce_ctor(x.base),x.name)
                    if isinstance(x,(Binary,Compare,Logical)):
                        if isinstance(x,Logical): return Logical(x.op,reduce_ctor(x.left),reduce_ctor(x.right) if x.right is not None else None)
                        return type(x)(x.op,reduce_ctor(x.left),reduce_ctor(x.right))
                    if isinstance(x,Call): return Call(x.name,tuple(reduce_ctor(a) for a in x.args))
                    return x
                pred=reduce_ctor(pred)
            transformed=replace(o,predicate=replace(o.predicate,expr=pred))
            (filters_pre if oi < first_sort_pos else filters_post).append(transformed)
    transformed_post_filters = {op.result: op for op in filters_post}
    post_tail = [transformed_post_filters.get(op.result, op) if isinstance(op, FilterOp) else op
                 for op in chain[last_sort_pos+1:]]
    chain=filters_pre + pre_maps + sort_ops + post_tail
    def path_field(expr):
        if isinstance(expr, (Field, Property)):
            if isinstance(expr.base, Name) and expr.base.name in {"row", "item"}:
                return expr.name
            parent=path_field(expr.base)
            return f"{parent}__{expr.name}" if parent else None
        return None

    sort_fields=[]
    for sort_stage in sort_ops:
        sort_field=path_field(sort_stage.spec.expr)
        if sort_field not in fields:
            raise ValueError("native record sort requires a top-level scalar row field")
        sort_fields.append((sort_stage, sort_field, fields[sort_field].name))

    # Literal record fields become parallel arrays. Sorting swaps every field
    # together, preserving the record association and stable ordering.
    globals_data=[]
    flattened_rows=[record_leaf_values(row, rn) for row in rows]
    for fname,ft in fields.items():
        vals=[row[fname] for row in flattened_rows]
        globals_data.append((fname,ft.name,vals))

    lines=["; ModuleID = 'slang-record-sort'", 'source_filename = "slang"', '']
    arrays={}
    for fname,ft,vals in globals_data:
        key=f"rcs_{fname}"
        llvm={'Number':'double','Boolean':'i1','Text':'ptr'}[ft]
        if ft=='Number':
            if not all(isinstance(v,(int,float)) and not isinstance(v,bool) for v in vals):
                raise ValueError(f"record field '{fname}' requires numeric literals")
            elems=', '.join(f"double {float(v):.17e}" for v in vals) or 'double 0.0'
            lines.append(f"@{key} = private constant [{len(vals) if vals else 1} x double] [{elems}]")
        elif ft=='Boolean':
            if not all(isinstance(v,bool) for v in vals):
                raise ValueError(f"record field '{fname}' requires Boolean literals")
            elems=', '.join('i1 1' if v else 'i1 0' for v in vals) or 'i1 0'
            lines.append(f"@{key} = private constant [{len(vals) if vals else 1} x i1] [{elems}]")
        else:
            ptrs=[]
            for j,v in enumerate(vals):
                if not isinstance(v,str): raise ValueError(f"record field '{fname}' requires Text literals")
                g=f"rcs_text_{fname}_{j}"; enc,l=_llvm_c_string(v)
                lines.append(f'@{g} = private constant [{l} x i8] c"{enc}"')
                ptrs.append(f"ptr getelementptr inbounds ([{l} x i8], ptr @{g}, i64 0, i64 0)")
            lines.append(f"@{key} = private constant [{len(vals) if vals else 1} x ptr] [{', '.join(ptrs)}]")
        arrays[fname]=(key,ft)

    lines += ['', 'declare ptr @malloc(i64)', 'declare void @free(ptr)', 'declare i32 @printf(ptr, ...)', 'declare i32 @strcmp(ptr, ptr)', 'declare double @slang_reduce_f64(ptr, i64, double, i32)',
              '@rcs_num_fmt = private constant [7 x i8] c"%.15g\\0A\\00"',
              '@rcs_text_fmt = private constant [4 x i8] c"%s\\0A\\00"',
              '@rcs_bool_fmt = private constant [4 x i8] c"%s\\0A\\00"',
              '@rcs_empty_msg = private constant [49 x i8] c"aggregate cannot operate on an empty collection\\0A\\00"',
              '@rcs_true = private constant [5 x i8] c"true\\00"',
              '@rcs_false = private constant [6 x i8] c"false\\00"',
              'define i32 @main() {', 'entry:']
    n=len(rows); cap=max(n,1)
    current='entry'; desc={}
    # Materialize the initial record arrays.
    for fname,ft,_ in globals_data:
        llvm={'Number':'double','Boolean':'i1','Text':'ptr'}[ft]
        buf=f"%src_{fname}"; lines.append(f"  {buf} = alloca [{cap} x {llvm}]")
        key=arrays[fname][0]
        for i in range(n):
            sp=f"%sp_{fname}_{i}"; sv=f"%sv_{fname}_{i}"; dp=f"%dp_{fname}_{i}"
            lines += [f"  {sp} = getelementptr inbounds [{n if n else 1} x {llvm}], ptr @{key}, i64 0, i64 {i}",
                      f"  {sv} = load {llvm}, ptr {sp}", f"  {dp} = getelementptr [{cap} x {llvm}], ptr {buf}, i64 0, i64 {i}", f"  store {llvm} {sv}, ptr {dp}"]
        desc[fname]=(buf,ft)

    # Pre-sort filters operate on record indices and copy all fields together.
    filter_ops=[op for op in chain[:chain.index(sort)] if isinstance(op,FilterOp)]
    for serial,op in enumerate(filter_ops,1):
        out={}
        for fname,ft,_ in globals_data:
            llvm={'Number':'double','Boolean':'i1','Text':'ptr'}[ft]
            out[fname]=f"%fbuf_{serial}_{fname}"; lines.append(f"  {out[fname]} = alloca [{cap} x {llvm}]")
        cnt=f"%fcnt_{serial}"; lines += [f"  {cnt} = alloca i64", f"  store i64 0, ptr {cnt}", f"  br label %fl_{serial}", f"fl_{serial}:",
            f"  %fi_{serial} = phi i64 [ 0, %{current} ], [ %fn_{serial}, %fs_{serial} ]",
            f"  %fc_{serial} = icmp ult i64 %fi_{serial}, {n}", f"  br i1 %fc_{serial}, label %fb_{serial}, label %fd_{serial}", f"fb_{serial}:"]
        refs={}
        for fname,ft,_ in globals_data:
            llvm={'Number':'double','Boolean':'i1','Text':'ptr'}[ft]; srcbuf=desc[fname][0]; pth=f"%fp_{serial}_{fname}"; val=f"%fv_{serial}_{fname}"
            lines += [f"  {pth} = getelementptr [{cap} x {llvm}], ptr {srcbuf}, i64 0, i64 %fi_{serial}", f"  {val} = load {llvm}, ptr {pth}"]
            refs[fname]=(ft,val)
        def pred(e):
            if isinstance(e,Logical):
                if e.op=='not':
                    a=pred(e.left); z=f"%fnot_{serial}_{len(lines)}"; lines.append(f"  {z} = xor i1 {a}, true"); return z
                a=pred(e.left); b=pred(e.right); z=f"%flog_{serial}_{len(lines)}"; lines.append(f"  {z} = {e.op} i1 {a}, {b}"); return z
            if not isinstance(e,Compare): raise ValueError("native record sort filter requires comparisons")
            lf=path_field(e.left); rf=path_field(e.right)
            def operand(x,f):
                if f:
                    return refs[f][0],refs[f][1]
                if isinstance(x,Binary) and x.op in {'+','-','*','/'}:
                    at,av=operand(x.left,path_field(x.left)); bt,bv=operand(x.right,path_field(x.right))
                    if at != 'Number' or bt != 'Number':
                        raise ValueError("native record sort filter arithmetic requires Number")
                    tmp=f"%fexpr_{serial}_{len(lines)}"
                    opmap={'+':'fadd','-':'fsub','*':'fmul','/':'fdiv'}[x.op]
                    lines.append(f"  {tmp} = {opmap} double {av}, {bv}")
                    return 'Number',tmp
                if isinstance(x,Literal):
                    if isinstance(x.value,bool): return 'Boolean','1' if x.value else '0'
                    if isinstance(x.value,str):
                        g=f"filter_str_{serial}_{len(lines)}"; enc,l=_llvm_c_string(x.value); lines.append(f'  %dummy_{serial}_{len(lines)} = alloca i8'); lines.append(f"  ; literal {x.value!r}")
                        # Use a private global inserted immediately before main is safer than an alloca.
                        raise ValueError("text literal filters in record sort are not yet supported")
                    if isinstance(x.value,(int,float)): return 'Number',format(float(x.value),'.17e')
                raise ValueError("unsupported record sort filter operand")
            a=operand(e.left,lf); b=operand(e.right,rf)
            if a[0]!=b[0]: raise ValueError("record sort filter comparison types must match")
            z=f"%fcmp_{serial}_{len(lines)}"
            if a[0]=='Number':
                pm={'>':'ogt','>=':'oge','<':'olt','<=':'ole','==':'oeq','!=':'one'}; lines.append(f"  {z} = fcmp {pm[e.op]} double {a[1]}, {b[1]}")
            elif a[0]=='Boolean':
                if e.op not in {'==','!='}: raise ValueError("Boolean filter supports == and !=")
                lines.append(f"  {z} = icmp {'eq' if e.op=='==' else 'ne'} i1 {a[1]}, {b[1]}")
            else:
                lines.append(f"  %fcmpv_{serial}_{len(lines)} = call i32 @strcmp(ptr {a[1]}, ptr {b[1]})")
                cv=f"%fcmpv_{serial}_{len(lines)-1}"; pm={'==':'eq','!=':'ne','>':'sgt','>=':'sge','<':'slt','<=':'sle'}
                if e.op not in pm: raise ValueError("unsupported Text filter operator")
                lines.append(f"  {z} = icmp {pm[e.op]} i32 {cv}, 0")
            return z
        keep=pred(op.predicate.expr)
        lines += [f"  br i1 {keep}, label %fk_{serial}, label %fs_{serial}", f"fk_{serial}:", f"  %fo_{serial} = load i64, ptr {cnt}"]
        for fname,ft,_ in globals_data:
            llvm={'Number':'double','Boolean':'i1','Text':'ptr'}[ft]; src=desc[fname][0]
            sp=f"%fcp_{serial}_{fname}"; sv=f"%fcv_{serial}_{fname}"; dp=f"%fdp_{serial}_{fname}"
            lines += [f"  {sp} = getelementptr [{cap} x {llvm}], ptr {src}, i64 0, i64 %fi_{serial}", f"  {sv} = load {llvm}, ptr {sp}", f"  {dp} = getelementptr [{cap} x {llvm}], ptr {out[fname]}, i64 0, i64 %fo_{serial}", f"  store {llvm} {sv}, ptr {dp}"]
        lines += [f"  %fon_{serial} = add i64 %fo_{serial}, 1", f"  store i64 %fon_{serial}, ptr {cnt}", f"  br label %fs_{serial}", f"fs_{serial}:", f"  %fn_{serial} = add i64 %fi_{serial}, 1", f"  br label %fl_{serial}", f"fd_{serial}:"]
        for fname in desc: desc[fname]=(out[fname],desc[fname][1])
        nref=f"%filter_count_{serial}"; lines.append(f"  {nref} = load i64, ptr {cnt}"); n=nref; current=f"fd_{serial}"

    # Record-preserving maps before sort are lowered as a field-wise transform.
    # The public value remains List<Record<T>> and every field is carried
    # together, so the later stable sort still preserves row association.
    pre_map_ops=[]
    for _op in chain:
        if isinstance(_op, SortOp): break
        if isinstance(_op, MapOp): pre_map_ops.append(_op)
    if pre_map_ops:
        for serial,op in enumerate(pre_map_ops,1):
            if not (isinstance(op.expr,Call) and op.expr.name in records):
                raise ValueError("native record sort pre-map must construct the same Record type")
            if op.expr.name != rn or len(op.expr.args) != len(decl.fields):
                raise ValueError("native record sort pre-map must construct the same Record type")
            out={}
            for fname,ft,_ in globals_data:
                llvm={'Number':'double','Boolean':'i1','Text':'ptr'}[ft]
                out[fname]=f"%prebuf_{serial}_{fname}"
                lines.append(f"  {out[fname]} = alloca [{cap} x {llvm}]")
            loop=f"pre_l_{serial}"; body=f"pre_b_{serial}"; done=f"pre_d_{serial}"
            lines += [f"  br label %{loop}",f"{loop}:",f"  %pre_i_{serial} = phi i64 [ 0, %{current} ], [ %pre_n_{serial}, %{body} ]",f"  %pre_c_{serial} = icmp ult i64 %pre_i_{serial}, {n}",f"  br i1 %pre_c_{serial}, label %{body}, label %{done}",f"{body}:"]
            refs={}
            for fname,ft,_ in globals_data:
                llvm={'Number':'double','Boolean':'i1','Text':'ptr'}[ft]
                sp=f"%pre_sp_{serial}_{fname}"; sv=f"%pre_sv_{serial}_{fname}"
                lines += [f"  {sp} = getelementptr [{cap} x {llvm}], ptr {desc[fname][0]}, i64 0, i64 %pre_i_{serial}",f"  {sv} = load {llvm}, ptr {sp}"]
                refs[fname]=(ft,sv)

            def pre_expr(e):
                if isinstance(e,Field) and isinstance(e.base,Name) and e.base.name in {"row","item"}:
                    if e.name not in refs: raise ValueError(f"unknown record field '{e.name}' in native pre-map")
                    return refs[e.name]
                if isinstance(e,Property) and isinstance(e.base,Name) and e.base.name in {"row","item"}:
                    if e.name not in refs: raise ValueError(f"unknown record field '{e.name}' in native pre-map")
                    return refs[e.name]
                if isinstance(e,Literal):
                    if isinstance(e.value,bool): return "Boolean", "1" if e.value else "0"
                    if isinstance(e.value,(int,float)) and not isinstance(e.value,bool): return "Number", format(float(e.value),'.17e')
                    if isinstance(e.value,str):
                        enc,l=_llvm_c_string(e.value); g=f"@pre_text_{serial}_{len(lines)}"
                        lines.append(f'  ; text literal {e.value!r}')
                        # Globals must be emitted before main; keep text literals
                        # unsupported here rather than generating invalid LLVM.
                        raise ValueError("native record sort pre-map Text literals are not yet supported")
                if isinstance(e,Binary) and e.op in {"+","-","*","/"}:
                    at,av=pre_expr(e.left); bt,bv=pre_expr(e.right)
                    if at!="Number" or bt!="Number": raise ValueError("native record pre-map arithmetic requires Number")
                    tmp=f"%pre_expr_{serial}_{len(lines)}"; opmap={"+":"fadd","-":"fsub","*":"fmul","/":"fdiv"}[e.op]
                    lines.append(f"  {tmp} = {opmap} double {av}, {bv}"); return "Number",tmp
                if isinstance(e,Compare):
                    at,av=pre_expr(e.left); bt,bv=pre_expr(e.right)
                    if at!=bt: raise ValueError("native record pre-map comparison types must match")
                    tmp=f"%pre_cmp_{serial}_{len(lines)}"
                    if at=="Number":
                        pm={'>':'ogt','>=':'oge','<':'olt','<=':'ole','==':'oeq','!=':'one'}
                        lines.append(f"  {tmp} = fcmp {pm[e.op]} double {av}, {bv}")
                    elif at=="Boolean" and e.op in {"==","!="}:
                        lines.append(f"  {tmp} = icmp {'eq' if e.op=='==' else 'ne'} i1 {av}, {bv}")
                    else: raise ValueError("native record pre-map comparison is unsupported")
                    return "Boolean",tmp
                raise ValueError("native record sort pre-map expression is unsupported")

            for (fname,ft),arg in zip(decl.fields,op.expr.args):
                typ,val=pre_expr(arg)
                if typ != ft.name: raise ValueError(f"native record pre-map field '{fname}' type mismatch")
                llvm={'Number':'double','Boolean':'i1','Text':'ptr'}[typ]
                dp=f"%pre_dp_{serial}_{fname}"
                lines += [f"  {dp} = getelementptr [{cap} x {llvm}], ptr {out[fname]}, i64 0, i64 %pre_i_{serial}",f"  store {llvm} {val}, ptr {dp}"]
            lines += [f"  %pre_n_{serial} = add i64 %pre_i_{serial}, 1",f"  br label %{loop}",f"{done}:"]
            for fname,ft,_ in globals_data:
                desc[fname]=(out[fname],ft)
            current=done

    # Stable bubble sort. Swap every record field whenever the key is out of order.
    for fname,ft,_ in globals_data:
        llvm={'Number':'double','Boolean':'i1','Text':'ptr'}[ft]; buf=f"%sbuf_{fname}"; lines.append(f"  {buf} = alloca [{cap} x {llvm}]")
        src=desc[fname][0]
        lines += [f"  br label %copy_{fname}", f"copy_{fname}:", f"  %ci_{fname} = phi i64 [ 0, %{current} ], [ %cn_{fname}, %cb_{fname} ]", f"  %cc_{fname} = icmp ult i64 %ci_{fname}, {n}", f"  br i1 %cc_{fname}, label %cb_{fname}, label %copydone_{fname}", f"cb_{fname}:"]
        sp=f"%csp_{fname}"; sv=f"%csv_{fname}"; dp=f"%cdp_{fname}"
        lines += [f"  {sp} = getelementptr [{cap} x {llvm}], ptr {src}, i64 0, i64 %ci_{fname}", f"  {sv} = load {llvm}, ptr {sp}", f"  {dp} = getelementptr [{cap} x {llvm}], ptr {buf}, i64 0, i64 %ci_{fname}", f"  store {llvm} {sv}, ptr {dp}", f"  %cn_{fname} = add i64 %ci_{fname}, 1", f"  br label %copy_{fname}", f"copydone_{fname}:"]
        desc[fname]=(buf,ft); current=f"copydone_{fname}"
    # Apply each stable sort pass in source order. A sequence such as
    # `sort by score desc` followed by `sort by group asc` therefore preserves
    # score ordering within equal groups, matching stable interpreter sorting.
    for sort_index, (sort_stage, sort_field, sort_type) in enumerate(sort_fields):
        keybuf,keytype=desc[sort_field]
        suffix=f"_{sort_index}"
        outer=f"sort_outer{suffix}"
        inner_init=f"sort_inner_init{suffix}"
        inner=f"sort_inner{suffix}"
        body=f"sort_body{suffix}"
        swap_label=f"sort_swap{suffix}"
        no_swap=f"sort_no_swap{suffix}"
        advance=f"sort_adv{suffix}"
        done="sort_done" if sort_index == len(sort_fields)-1 else f"sort_done{suffix}"
        so=f"%so{suffix}"; sn=f"%sn{suffix}"; solim=f"%solim{suffix}"; soc=f"%soc{suffix}"
        sj=f"%sj{suffix}"; sic=f"%sic{suffix}"; srj=f"%srj{suffix}"
        slp=f"%slp{suffix}"; srp=f"%srp{suffix}"; sl=f"%sl{suffix}"; sr=f"%sr{suffix}"
        outer_next=f"%sonext{suffix}"
        lines += [f"  br label %{outer}", outer+":", f"  {so} = phi i64 [ 0, %{current} ], [ {outer_next}, %{advance} ]",
                  f"  {sn} = add i64 0, {n}", f"  {solim} = sub i64 {sn}, 1",
                  f"  {soc} = icmp ult i64 {so}, {solim}",
                  f"  br i1 {soc}, label %{inner_init}, label %{done}",
                  inner_init+":", f"  br label %{inner}", inner+":",
                  f"  {sj} = phi i64 [ 0, %{inner_init} ], [ %sjn{suffix}, %{no_swap} ]",
                  f"  {sic} = icmp ult i64 {sj}, {solim}",
                  f"  br i1 {sic}, label %{body}, label %{advance}", body+":"]
        kllvm={'Number':'double','Boolean':'i1','Text':'ptr'}[keytype]
        lines += [f"  {slp} = getelementptr [{cap} x {kllvm}], ptr {keybuf}, i64 0, i64 {sj}",
                  f"  {srj} = add i64 {sj}, 1",
                  f"  {srp} = getelementptr [{cap} x {kllvm}], ptr {keybuf}, i64 0, i64 {srj}",
                  f"  {sl} = load {kllvm}, ptr {slp}", f"  {sr} = load {kllvm}, ptr {srp}"]
        swap=f"%swap{suffix}"
        if keytype=='Number':
            cmp='ogt' if sort_stage.spec.ascending else 'olt'
            lines.append(f"  {swap} = fcmp {cmp} double {sl}, {sr}")
        elif keytype=='Boolean':
            cmpop='ugt' if sort_stage.spec.ascending else 'ult'
            lines.append(f"  {swap} = icmp {cmpop} i1 {sl}, {sr}")
        else:
            scmp=f"%scmp{suffix}"
            lines += [f"  {scmp} = call i32 @strcmp(ptr {sl}, ptr {sr})",
                      f"  {swap} = icmp {'sgt' if sort_stage.spec.ascending else 'slt'} i32 {scmp}, 0"]
        lines += [f"  br i1 {swap}, label %{swap_label}, label %{no_swap}", swap_label+":"]
        for fname,ft,_ in globals_data:
            llvm={'Number':'double','Boolean':'i1','Text':'ptr'}[ft]; buf=desc[fname][0]
            lp=f"%lp{suffix}_{fname}"; rp=f"%rp{suffix}_{fname}"
            lv=f"%lv{suffix}_{fname}"; rv=f"%rv{suffix}_{fname}"
            lines += [f"  {lp} = getelementptr [{cap} x {llvm}], ptr {buf}, i64 0, i64 {sj}",
                      f"  {rp} = getelementptr [{cap} x {llvm}], ptr {buf}, i64 0, i64 {srj}",
                      f"  {lv} = load {llvm}, ptr {lp}", f"  {rv} = load {llvm}, ptr {rp}",
                      f"  store {llvm} {rv}, ptr {lp}", f"  store {llvm} {lv}, ptr {rp}"]
        lines += [f"  br label %{no_swap}", no_swap+":", f"  %sjn{suffix} = add i64 {sj}, 1",
                  f"  br label %{inner}", advance+":",
                  f"  {outer_next} = add i64 {so}, 1", f"  br label %{outer}", done+":"]
        current=done

    # 1.8.77: post-sort filters are lowered as real record compaction stages.
    # Earlier versions preserved the filter semantically but still fed the
    # unfiltered sorted buffers into later maps/terminals. Each post-sort filter
    # now copies matching whole records together and updates the live row count.
    post_sort_filters=[op for op in chain if isinstance(op,FilterOp) and chain.index(op)>chain.index(sort)]
    for serial,op in enumerate(post_sort_filters,1):
        out={}
        for fname,ft,_ in globals_data:
            llvm={'Number':'double','Boolean':'i1','Text':'ptr'}[ft]
            out[fname]=f"%psfbuf_{serial}_{fname}"
            lines.append(f"  {out[fname]} = alloca [{cap} x {llvm}]")
        cnt=f"%psfcnt_{serial}"
        predecessor='sort_done' if serial == 1 else f'post_filter_done_{serial-1}'
        lines += [f"  {cnt} = alloca i64", f"  store i64 0, ptr {cnt}",
                  f"  br label %post_filter_loop_{serial}", f"post_filter_loop_{serial}:",
                  f"  %psfi_{serial} = phi i64 [ 0, %{predecessor} ], [ %psfn_{serial}, %post_filter_skip_{serial} ]",
                  f"  %psfcond_{serial} = icmp ult i64 %psfi_{serial}, {n}",
                  f"  br i1 %psfcond_{serial}, label %post_filter_body_{serial}, label %post_filter_done_{serial}",
                  f"post_filter_body_{serial}:"]
        refs={}
        for fname,ft,_ in globals_data:
            llvm={'Number':'double','Boolean':'i1','Text':'ptr'}[ft]
            sp=f"%psfsp_{serial}_{fname}"; sv=f"%psfsv_{serial}_{fname}"
            lines += [f"  {sp} = getelementptr [{cap} x {llvm}], ptr {desc[fname][0]}, i64 0, i64 %psfi_{serial}",
                       f"  {sv} = load {llvm}, ptr {sp}"]
            refs[fname]=(ft,sv)
        def ps_pred(e):
            if isinstance(e,Logical):
                if e.op=='not':
                    a=ps_pred(e.left); z=f"%psfnot_{serial}_{len(lines)}"; lines.append(f"  {z} = xor i1 {a}, true"); return z
                a=ps_pred(e.left); b=ps_pred(e.right); z=f"%psflog_{serial}_{len(lines)}"; lines.append(f"  {z} = {e.op} i1 {a}, {b}"); return z
            if not isinstance(e,Compare):
                raise ValueError("native post-sort record filter requires comparisons")
            def operand(x):
                f=path_field(x)
                if f:
                    if f not in refs: raise ValueError(f"unknown record field '{f}' in native post-sort filter")
                    return refs[f]
                if isinstance(x,Binary) and x.op in {'+','-','*','/'}:
                    at,av=operand(x.left); bt,bv=operand(x.right)
                    if at!='Number' or bt!='Number': raise ValueError("native post-sort filter arithmetic requires Number")
                    z=f"%psfar_{serial}_{len(lines)}"; opmap={'+':'fadd','-':'fsub','*':'fmul','/':'fdiv'}; lines.append(f"  {z} = {opmap[x.op]} double {av}, {bv}")
                    return 'Number',z
                if isinstance(x,Literal):
                    if isinstance(x.value,bool): return 'Boolean','1' if x.value else '0'
                    if isinstance(x.value,(int,float)) and not isinstance(x.value,bool): return 'Number',format(float(x.value),'.17e')
                    if isinstance(x.value,str):
                        enc,l=_llvm_c_string(x.value); g=f"psf_text_{serial}_{len(lines)}"
                        lines.insert(2, f'@{g} = private constant [{l} x i8] c"{enc}"')
                        return 'Text', f"getelementptr inbounds ([{l} x i8], ptr @{g}, i64 0, i64 0)"
                raise ValueError("unsupported native post-sort filter operand")
            a=operand(e.left); b=operand(e.right)
            if a[0]!=b[0]: raise ValueError("native post-sort filter comparison types must match")
            z=f"%psfcmp_{serial}_{len(lines)}"
            if a[0]=='Number':
                pm={'>':'ogt','>=':'oge','<':'olt','<=':'ole','==':'oeq','!=':'one'}; lines.append(f"  {z} = fcmp {pm[e.op]} double {a[1]}, {b[1]}")
            elif a[0]=='Boolean' and e.op in {'==','!='}:
                lines.append(f"  {z} = icmp {'eq' if e.op=='==' else 'ne'} i1 {a[1]}, {b[1]}")
            elif a[0]=='Text' and e.op in {'==','!='}:
                cmpv=f"%psftextcmp_{serial}_{len(lines)}"
                lines.append(f"  {cmpv} = call i32 @strcmp(ptr {a[1]}, ptr {b[1]})")
                lines.append(f"  {z} = icmp {'eq' if e.op=='==' else 'ne'} i32 {cmpv}, 0")
            else:
                raise ValueError("native post-sort filter currently supports Number, Boolean, and Text comparisons")
            return z
        keep=ps_pred(op.predicate.expr)
        lines += [f"  br i1 {keep}, label %post_filter_keep_{serial}, label %post_filter_skip_{serial}", f"post_filter_keep_{serial}:", f"  %psfo_{serial} = load i64, ptr {cnt}"]
        for fname,ft,_ in globals_data:
            llvm={'Number':'double','Boolean':'i1','Text':'ptr'}[ft]
            sp=f"%psfcp_{serial}_{fname}"; sv=f"%psfcv_{serial}_{fname}"; dp=f"%psfdp_{serial}_{fname}"
            lines += [f"  {sp} = getelementptr [{cap} x {llvm}], ptr {desc[fname][0]}, i64 0, i64 %psfi_{serial}",
                       f"  {sv} = load {llvm}, ptr {sp}",
                       f"  {dp} = getelementptr [{cap} x {llvm}], ptr {out[fname]}, i64 0, i64 %psfo_{serial}",
                       f"  store {llvm} {sv}, ptr {dp}"]
        lines += [f"  %psfon_{serial} = add i64 %psfo_{serial}, 1", f"  store i64 %psfon_{serial}, ptr {cnt}", f"  br label %post_filter_skip_{serial}",
                  f"post_filter_skip_{serial}:", f"  %psfn_{serial} = add i64 %psfi_{serial}, 1", f"  br label %post_filter_loop_{serial}", f"post_filter_done_{serial}:"]
        for fname,ft,_ in globals_data:
            desc[fname]=(out[fname],ft)
        n=f"%psfn_value_{serial}"
        lines.append(f"  {n} = load i64, ptr {cnt}")

    # 1.8.75: Record -> Record maps are also allowed after the stable sort.
    # The sort has already reordered the complete record buffers, so each
    # post-sort record transform consumes those reordered buffers and produces
    # a new complete record buffer before any scalar projection or terminal
    # operation. The function is inlined to the same pure Record constructor
    # form used by the pre-sort path; no second collection representation is
    # exposed to S-Lang.
    post_sort_maps=[op for op in chain if isinstance(op,MapOp) and chain.index(op)>chain.index(sort)]
    record_post_maps=[]
    scalar_post_maps=[]
    for op in post_sort_maps:
        if isinstance(op.expr, Call) and op.expr.name == rn:
            record_post_maps.append(op)
            continue
        if isinstance(op.expr, Call) and op.expr.name in fn_by_name:
            inlined=inline_record_function(op.expr)
            if isinstance(inlined, Call) and inlined.name == rn:
                op=replace(op, expr=inlined)
                record_post_maps.append(op)
                continue
        scalar_post_maps.append(op)

    post_record_done='sort_done'
    for serial,op in enumerate(record_post_maps, 1):
        if not (isinstance(op.expr, Call) and op.expr.name == rn):
            raise ValueError("native record sort post-map must construct the same Record type")
        if len(op.expr.args) != len(decl.fields):
            raise ValueError("native record sort post-map constructor arity mismatch")
        bufs={}
        for fname,ft,_ in globals_data:
            llvm_typ={'Number':'double','Boolean':'i1','Text':'ptr'}[ft]
            bufs[fname]=f"%postbuf_{serial}_{fname}"
            lines.append(f"  {bufs[fname]} = alloca [{cap} x {llvm_typ}]")
        loop=f"post_l_{serial}"; body=f"post_b_{serial}"; done=f"post_d_{serial}"
        if serial == 1:
            predecessor = f'post_filter_done_{len(post_sort_filters)}' if post_sort_filters else 'sort_done'
        else:
            predecessor = f'post_d_{serial-1}'
        lines += [f"  br label %{loop}", f"{loop}:",
                  f"  %post_i_{serial} = phi i64 [ 0, %{predecessor} ], [ %post_n_{serial}, %{body} ]",
                  f"  %post_c_{serial} = icmp ult i64 %post_i_{serial}, {n}",
                  f"  br i1 %post_c_{serial}, label %{body}, label %{done}", f"{body}:"]
        ptrs={}
        for fname,ft,_ in globals_data:
            llvm_typ={'Number':'double','Boolean':'i1','Text':'ptr'}[ft]
            ptr=f"%post_srcptr_{serial}_{fname}"
            lines.append(f"  {ptr} = getelementptr [{cap} x {llvm_typ}], ptr {desc[fname][0]}, i64 0, i64 %post_i_{serial}")
            ptrs[fname]=ptr

        def post_expr(e, expected):
            if isinstance(e, Field) and isinstance(e.base, Name) and e.base.name in {'row','item'}:
                if e.name not in ptrs:
                    raise ValueError(f"unknown record field '{e.name}' in native post-map")
                _,ft=decl.fields[[x[0] for x in decl.fields].index(e.name)]
                llvm_t={'Number':'double','Boolean':'i1','Text':'ptr'}[ft.name]
                v=f"%post_v_{serial}_{e.name}_{len(lines)}"
                lines.append(f"  {v} = load {llvm_t}, ptr {ptrs[e.name]}")
                return ft.name, v
            if isinstance(e, Property) and isinstance(e.base, Name) and e.base.name in {'row','item'}:
                if e.name not in ptrs:
                    raise ValueError(f"unknown record field '{e.name}' in native post-map")
                _,ft=decl.fields[[x[0] for x in decl.fields].index(e.name)]
                llvm_t={'Number':'double','Boolean':'i1','Text':'ptr'}[ft.name]
                v=f"%post_v_{serial}_{e.name}_{len(lines)}"
                lines.append(f"  {v} = load {llvm_t}, ptr {ptrs[e.name]}")
                return ft.name, v
            if isinstance(e, Literal):
                if isinstance(e.value,bool): return 'Boolean', '1' if e.value else '0'
                if isinstance(e.value,(int,float)) and not isinstance(e.value,bool): return 'Number', f"{float(e.value):.17e}"
                if isinstance(e.value,str):
                    enc,l=_llvm_c_string(e.value); g=f"post_text_{serial}_{len(lines)}"
                    lines.insert(2, f'@{g} = private constant [{l} x i8] c"{enc}"')
                    return 'Text', f"getelementptr inbounds ([{l} x i8], ptr @{g}, i64 0, i64 0)"
                raise ValueError("unsupported literal in native post-map")
            if isinstance(e, Binary) and e.op in {'+','-','*','/'}:
                at,av=post_expr(e.left, expected); bt,bv=post_expr(e.right, expected)
                if at!='Number' or bt!='Number': raise ValueError("native post-map arithmetic requires Number")
                opx={'+':'fadd','-':'fsub','*':'fmul','/':'fdiv'}[e.op]; v=f"%post_ar_{serial}_{len(lines)}"; lines.append(f"  {v} = {opx} double {av}, {bv}"); return 'Number',v
            raise ValueError("native record sort post-map supports row fields, literals, and numeric arithmetic")

        for (fname,ft,_),arg in zip(globals_data,op.expr.args):
            typ,val=post_expr(arg,ft)
            if typ != ft: raise ValueError(f"native post-map field '{fname}' type mismatch")
            llvm_typ={'Number':'double','Boolean':'i1','Text':'ptr'}[typ]
            dp=f"%post_dst_{serial}_{fname}"
            lines.append(f"  {dp} = getelementptr [{cap} x {llvm_typ}], ptr {bufs[fname]}, i64 0, i64 %post_i_{serial}")
            lines.append(f"  store {llvm_typ} {val}, ptr {dp}")
        lines += [f"  %post_n_{serial} = add i64 %post_i_{serial}, 1", f"  br label %{loop}", f"{done}:"]
        post_record_done=done
        for fname,ft,_ in globals_data:
            desc[fname]=(bufs[fname],ft)

    # The live control-flow predecessor after all post-sort structured stages.
    # A scalar projection or terminal operation must start from the final
    # compacted/transformed record buffer, not directly from `sort_done`.
    if record_post_maps:
        terminal_predecessor = post_record_done
    elif post_sort_filters:
        terminal_predecessor = f'post_filter_done_{len(post_sort_filters)}'
    else:
        terminal_predecessor = 'sort_done'

    # Terminal scalar projection or terminal reduction/aggregation.
    maps=scalar_post_maps
    if len(p.ast.aggregates) > 1 and not p.ast.reduces:
        aggs = list(p.ast.aggregates)
        if len({item.source for item in aggs}) != 1:
            raise ValueError("native record multi-aggregate requires one shared sorted collection")
        allowed = {"sum", "count", "min", "max", "average", "avg"}
        if any(item.operation not in allowed for item in aggs):
            raise ValueError("native record multi-aggregate received an unsupported terminal")
        source_name = aggs[0].source
        record_results = {sort.result} | {op.result for op in post_sort_filters} | {op.result for op in record_post_maps}
        scalar_source = bool(maps and source_name == maps[-1].result)
        if source_name not in record_results and not scalar_source:
            raise ValueError("native record multi-aggregate must consume the sorted record or one scalar projection")
        # Compose every scalar map after the sort, including maps separated
        # by filters. Filters have already been translated back to row-field
        # predicates above, so the terminal expression can be inlined too.
        scalar_value_expr = None
        if scalar_source:
            for scalar_map in reversed(maps):
                scalar_value_expr = scalar_map.expr if scalar_value_expr is None else substitute_record_expr(
                    scalar_value_expr, {"item": scalar_map.expr, "value": scalar_map.expr}
                )
        aggregate_exprs = []
        for item in aggs:
            if item.operation == "count":
                aggregate_exprs.append(None)
                continue
            expr = item.expr
            if scalar_source and isinstance(expr, Name) and expr.name in {"item", "value"}:
                expr = scalar_value_expr
            def validate_numeric_aggregate_expr(node):
                if isinstance(node, (Field, Property)):
                    fname = path_field(node)
                    if fname not in fields or fields[fname].name != "Number":
                        raise ValueError("native record aggregate expressions require numeric row fields")
                    return
                if isinstance(node, Literal) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                    return
                if isinstance(node, Binary) and node.op in {"+", "-", "*", "/"}:
                    validate_numeric_aggregate_expr(node.left)
                    validate_numeric_aggregate_expr(node.right)
                    return
                raise ValueError("native record multi-aggregate supports numeric row fields, literals and arithmetic")
            validate_numeric_aggregate_expr(expr)
            aggregate_exprs.append(expr)
        lines += ['', '  ; terminal record multi-aggregate: one shared scan']
        for j, item in enumerate(aggs):
            if item.operation != "count":
                init = "0x7FF0000000000000" if item.operation == "min" else "0xFFF0000000000000" if item.operation == "max" else "0.00000000000000000e+00"
                lines += [f"  %multi_acc_{j} = alloca double", f"  store double {init}, ptr %multi_acc_{j}"]
        lines += ["  br label %multi_agg_loop", "multi_agg_loop:",
                  f"  %multi_i = phi i64 [ 0, %{terminal_predecessor} ], [ %multi_next, %multi_agg_body ]",
                  f"  %multi_cond = icmp ult i64 %multi_i, {n}",
                  "  br i1 %multi_cond, label %multi_agg_body, label %multi_agg_done", "multi_agg_body:"]
        for j, item in enumerate(aggs):
            expr = aggregate_exprs[j]
            if expr is None:
                continue
            def emit_multi_value(node):
                if isinstance(node, (Field, Property)):
                    fname = path_field(node)
                    buf = desc[fname][0]
                    ptr = f"%multi_ptr_{j}_{len(lines)}"
                    val = f"%multi_field_{j}_{len(lines)}"
                    lines.extend([f"  {ptr} = getelementptr [{cap} x double], ptr {buf}, i64 0, i64 %multi_i",
                                  f"  {val} = load double, ptr {ptr}"])
                    return val
                if isinstance(node, Literal):
                    return f"{float(node.value):.17e}"
                if isinstance(node, Binary) and node.op in {"+", "-", "*", "/"}:
                    left = emit_multi_value(node.left)
                    right = emit_multi_value(node.right)
                    val = f"%multi_expr_{j}_{len(lines)}"
                    opcode = {"+": "fadd", "-": "fsub", "*": "fmul", "/": "fdiv"}[node.op]
                    lines.append(f"  {val} = {opcode} double {left}, {right}")
                    return val
                raise ValueError("unsupported native record aggregate expression")
            value_ref = emit_multi_value(expr)
            lines += [f"  %multi_value_{j} = fadd double 0.0, {value_ref}",
                      f"  %multi_old_{j} = load double, ptr %multi_acc_{j}"]
            op = item.operation
            if op in {"sum", "average", "avg"}:
                lines.append(f"  %multi_new_{j} = fadd double %multi_old_{j}, %multi_value_{j}")
            elif op == "min":
                lines += [f"  %multi_cmp_{j} = fcmp ogt double %multi_old_{j}, %multi_value_{j}",
                          f"  %multi_new_{j} = select i1 %multi_cmp_{j}, double %multi_value_{j}, double %multi_old_{j}"]
            else:
                lines += [f"  %multi_cmp_{j} = fcmp olt double %multi_old_{j}, %multi_value_{j}",
                          f"  %multi_new_{j} = select i1 %multi_cmp_{j}, double %multi_value_{j}, double %multi_old_{j}"]
            lines.append(f"  store double %multi_new_{j}, ptr %multi_acc_{j}")
        lines += ["  %multi_next = add i64 %multi_i, 1", "  br label %multi_agg_loop", "multi_agg_done:"]
        needs_nonempty = any(item.operation in {"min", "max", "average", "avg"} for item in aggs)
        if needs_nonempty:
            lines += [f"  %multi_has_rows = icmp ne i64 {n}, 0",
                      "  br i1 %multi_has_rows, label %multi_results, label %multi_empty",
                      "multi_empty:",
                      "  call i32 (ptr, ...) @printf(ptr @rcs_empty_msg)",
                      "  ret i32 1",
                      "multi_results:"]
        for j, item in enumerate(aggs):
            if not any(isinstance(sh.target, Name) and sh.target.name == item.result for sh in p.ast.shows):
                continue
            if item.operation == "count":
                if isinstance(n, str) and n.startswith("%"):
                    lines += [f"  %multi_count_double_{j} = uitofp i64 {n} to double",
                              f"  call i32 (ptr, ...) @printf(ptr @rcs_num_fmt, double %multi_count_double_{j})"]
                else:
                    lines.append(f"  call i32 (ptr, ...) @printf(ptr @rcs_num_fmt, double {float(n):.17e})")
                continue
            lines.append(f"  %multi_final_{j} = load double, ptr %multi_acc_{j}")
            result_value = f"%multi_final_{j}"
            if item.operation in {"average", "avg"}:
                if isinstance(n, str) and n.startswith("%"):
                    lines.append(f"  %multi_count_f_{j} = uitofp i64 {n} to double")
                    count_value = f"%multi_count_f_{j}"
                else:
                    count_value = f"{float(n):.17e}"
                lines += [f"  %multi_avg_{j} = fdiv double {result_value}, {count_value}"]
                result_value = f"%multi_avg_{j}"
            lines.append(f"  call i32 (ptr, ...) @printf(ptr @rcs_num_fmt, double {result_value})")
        lines += ['  ret i32 0', '}', '']
        return '\n'.join(lines)

    terminal = p.ast.reduces[0] if p.ast.reduces else (p.ast.aggregates[0] if p.ast.aggregates else None)
    if terminal is not None:
        # `count` is cardinality, not a field aggregation. The parser represents
        # it as a literal `1`, so requiring a field path here would incorrectly
        # reject `records count` and `records count row.name`.
        if isinstance(terminal, AggregateOp) and terminal.operation == 'count':
            record_count_sources={sort.result}
            record_count_sources.update(op.result for op in post_sort_filters)
            record_count_sources.update(op.result for op in record_post_maps)
            if terminal.source not in record_count_sources and not (maps and terminal.source == maps[-1].result):
                raise ValueError("native record count must consume the sorted record or its scalar projection")
            lines += ['', '  ; terminal record count']
            if isinstance(n,str) and n.startswith('%'):
                count_value=n
                count_double='%record_count_double'
                lines.append(f"  {count_double} = uitofp i64 {count_value} to double")
                result_value=count_double
            else:
                result_value=str(n)
                count_value=None
            if any(isinstance(sh.target,Name) and sh.target.name==terminal.result for sh in p.ast.shows):
                if count_value is not None:
                    lines.append(f"  call i32 (ptr, ...) @printf(ptr @rcs_num_fmt, double {result_value})")
                else:
                    lines.append(f"  call i32 (ptr, ...) @printf(ptr @rcs_num_fmt, double {float(n):.17e})")
            lines += ['  ret i32 0', '}', '']
            return '\n'.join(lines)
        # A terminal scalar map may feed the terminal operation. Otherwise the
        # terminal expression may directly address a field of the sorted record.
        record_result_names={op.result for op in record_post_maps}
        if terminal.source == sort.result or terminal.source in record_result_names:
            terminal_field = path_field(terminal.expr.right if isinstance(terminal, ReduceOp) and isinstance(terminal.expr, Binary) else terminal.expr)
            terminal_field = terminal_field or path_field(terminal.expr)
        elif maps and terminal.source == maps[-1].result:
            if len(maps) != 1:
                raise ValueError("native record terminal backend supports at most one scalar map after sort")
            terminal_field = path_field(maps[-1].expr)
        else:
            raise ValueError("native record terminal must consume the sorted record or one scalar projection")
        if terminal_field not in fields:
            raise ValueError("native record terminal must consume a scalar record field")
        if fields[terminal_field].name != 'Number':
            raise ValueError("native record reduce/aggregate currently requires a numeric field")
        if isinstance(terminal, ReduceOp):
            if not isinstance(terminal.initial, Literal) or not isinstance(terminal.initial.value,(int,float)):
                raise ValueError("native record reduce requires a numeric literal initial accumulator")
            if not isinstance(terminal.expr, Binary) or not isinstance(terminal.expr.left, Name) or terminal.expr.left.name != 'acc' or terminal.expr.op not in {'+','-','*','/'}:
                raise ValueError("native record reduce supports only acc <+|-|*|> item.field")
            rhs_field = path_field(terminal.expr.right)
            if rhs_field is None and isinstance(terminal.expr.right, Name) and terminal.expr.right.name == 'item':
                rhs_field = terminal_field
            if rhs_field != terminal_field:
                raise ValueError("native record reduce field must match its terminal source")
            opcode={'+':0,'-':1,'*':2,'/':3}[terminal.expr.op]
            lines += ['', '  ; terminal record reduce']
            ptr_name="%terminal_ptr"
            lines += [f"  {ptr_name} = getelementptr [{cap} x double], ptr {desc[terminal_field][0]}, i64 0, i64 0", f"  %terminal = call double @slang_reduce_f64(ptr {ptr_name}, i64 {n}, double {float(terminal.initial.value):.17e}, i32 {opcode})"]
            result_name=terminal.result
            if any(isinstance(sh.target,Name) and sh.target.name==result_name for sh in p.ast.shows):
                lines += [f"  call i32 (ptr, ...) @printf(ptr @rcs_num_fmt, double %terminal)"]
        else:
            if terminal.operation not in {'sum','count','min','max','average','avg'}:
                raise ValueError(f"unsupported native record aggregate '{terminal.operation}'")
            lines += ['', '  ; terminal record aggregate']
            buf=desc[terminal_field][0]
            lines += [f"  %aggacc = alloca double", f"  %aggcnt = alloca i64", "  store i64 0, ptr %aggcnt"]
            init='0.00000000000000000e+00'
            if terminal.operation=='min': init='0x7FF0000000000000'
            elif terminal.operation=='max': init='0xFFF0000000000000'
            lines += [f"  store double {init}, ptr %aggacc", "  br label %terminal_agg_loop", "terminal_agg_loop:", f"  %tai = phi i64 [ 0, %{terminal_predecessor} ], [ %tanext, %terminal_agg_body ]", f"  %tacond = icmp ult i64 %tai, {n}", "  br i1 %tacond, label %terminal_agg_body, label %terminal_agg_done", "terminal_agg_body:", f"  %tap = getelementptr [{cap} x double], ptr {buf}, i64 0, i64 %tai", "  %tav = load double, ptr %tap", "  %tcur = load double, ptr %aggacc"]
            if terminal.operation in {'sum','average','avg'}:
                lines += ["  %tnew = fadd double %tcur, %tav"]
            elif terminal.operation=='count':
                lines += ["  %tnew = fadd double %tcur, 1.00000000000000000e+00"]
            elif terminal.operation=='min':
                lines += ["  %tcmp = fcmp ogt double %tcur, %tav", "  %tnew = select i1 %tcmp, double %tav, double %tcur"]
            else:
                lines += ["  %tcmp = fcmp olt double %tcur, %tav", "  %tnew = select i1 %tcmp, double %tav, double %tcur"]
            lines += ["  store double %tnew, ptr %aggacc", "  %tc = load i64, ptr %aggcnt", "  %tnc = add i64 %tc, 1", "  store i64 %tnc, ptr %aggcnt", "  %tanext = add i64 %tai, 1", "  br label %terminal_agg_loop", "terminal_agg_done:", "  %tfinal = load double, ptr %aggacc"]
            if terminal.operation in {'average','avg'}:
                lines += ["  %tcount = load i64, ptr %aggcnt", "  %tcountf = uitofp i64 %tcount to double", "  %tavg = fdiv double %tfinal, %tcountf"]
                result_value='%tavg'
            else:
                result_value='%tfinal'
            if any(isinstance(sh.target,Name) and sh.target.name==terminal.result for sh in p.ast.shows):
                lines += [f"  call i32 (ptr, ...) @printf(ptr @rcs_num_fmt, double {result_value})"]
        lines += ['  ret i32 0', '}', '']
        return '\n'.join(lines)

    current=terminal_predecessor
    for mi,op in enumerate(maps,1):
        f=path_field(op.expr)
        if f not in fields: raise ValueError("native record sort map must project a scalar record field")
        ft=fields[f].name; llvm={'Number':'double','Boolean':'i1','Text':'ptr'}[ft]; buf=desc[f][0]
        loop=f"map_{mi}"; body=f"map_body_{mi}"; done=f"map_done_{mi}"
        lines += [f"  br label %{loop}", f"{loop}:", f"  %mi_{mi} = phi i64 [ 0, %{current} ], [ %mn_{mi}, %{body} ]", f"  %mc_{mi} = icmp ult i64 %mi_{mi}, {n}", f"  br i1 %mc_{mi}, label %{body}, label %{done}", f"{body}:", f"  %mp_{mi} = getelementptr [{cap} x {llvm}], ptr {buf}, i64 0, i64 %mi_{mi}", f"  %mv_{mi} = load {llvm}, ptr %mp_{mi}"]
        if ft=='Number': lines.append(f"  call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([7 x i8], ptr @rcs_num_fmt, i64 0, i64 0), double %mv_{mi})")
        elif ft=='Text': lines.append(f"  call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([4 x i8], ptr @rcs_text_fmt, i64 0, i64 0), ptr %mv_{mi})")
        else:
            bp=f"%mbp_{mi}"; lines += [f"  {bp} = select i1 %mv_{mi}, ptr getelementptr inbounds ([5 x i8], ptr @rcs_true, i64 0, i64 0), ptr getelementptr inbounds ([6 x i8], ptr @rcs_false, i64 0, i64 0)", f"  call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([4 x i8], ptr @rcs_bool_fmt, i64 0, i64 0), ptr {bp})"]
        lines += [f"  %mn_{mi} = add i64 %mi_{mi}, 1", f"  br label %{loop}", f"{done}:"]
        current=done
    if not maps:
        raise ValueError("native record sort requires a scalar map after sort so the result can be shown")
    lines += ['  ret i32 0', '}', '']
    return '\n'.join(lines)


def record_collection_llvm_ir(p: Program, schema_contract=None):
    """Lower List<Record<T>> literals through native collection operations.

    Record collections keep their public S-Lang type while numeric pipeline
    stages may be lowered through the existing collection backends after the
    record source is materialized as a semantic table. This keeps the native
    implementation shared instead of creating a second sort/reduce/aggregate
    algorithm specifically for records.
    """
    validate(p)
    # 1.10.37: backend field resolution uses the semantic schema contract as
    # the authoritative record layout. AST record declarations remain only
    # the source of operation expressions; field existence/type is not inferred
    # from them during lowering.
    records = {r.name: r for r in p.ast.records}
    schema_by_binding = {}
    for binding, in_schema, out_schema in (schema_contract or getattr(p, "_backend_schema_contract", ())):
        schema_by_binding[binding] = (in_schema, out_schema)

    def _schema_pair(binding):
        pair = schema_by_binding.get(binding)
        if pair is None:
            # ExecutionIR bindings are versioned (`name#N`), while AST
            # collection operations refer to the source value by its public
            # binding name. Resolve that deterministic correspondence without
            # inspecting record declarations.
            matches = [(k, v) for k, v in schema_by_binding.items() if k.split("#", 1)[0] == binding]
            if len(matches) == 1:
                pair = matches[0][1]
        return pair

    def _schema_fields(binding, output=True):
        pair = _schema_pair(binding)
        schema = pair[1 if output else 0] if pair else None
        if schema is None:
            return None
        return tuple((field.name, field.type_name) for field in getattr(schema, "fields", ()))

    def _schema_for_stage(binding, output=True):
        fields = _schema_fields(binding, output=output)
        if fields is None:
            return None
        return {name: typ for name, typ in fields}

    def _validate_expr_fields(expr, binding):
        fields = _schema_for_stage(binding, output=True)
        if fields is None:
            return
        def walk(e):
            if isinstance(e, (Field, Property)) and isinstance(e.base, Name) and e.base.name == "row":
                typ = fields.get(e.name)
                if typ is None:
                    raise ValueError(f"native backend schema contract for '{binding}' has no field '{e.name}'")
                if typ not in {"Number", "Boolean", "Text"}:
                    raise ValueError(f"native backend field '{binding}.row.{e.name}' has unsupported type {typ}")
                return
            if isinstance(e, (Binary, Compare, Logical)):
                walk(e.left)
                if getattr(e, "right", None) is not None: walk(e.right)
            elif isinstance(e, Conditional):
                walk(e.condition); walk(e.then_expr); walk(e.else_expr)
            elif isinstance(e, Call):
                for arg in e.args: walk(arg)
        walk(expr)

    # 1.10.86: when a pipeline projects a Record collection to a scalar
    # collection before sort, leave the structured-record backend at the
    # projection boundary and reuse the ordinary scalar sort pipeline. This
    # avoids treating the scalar result as a Record and also allows the normal
    # native function/sort lowering to handle expressions such as
    # `records map row.value`, `records map double(row.value)`, or a scalar
    # map after a Record filter.
    if p.ast.sorts:
        sort_stage = p.ast.sorts[0]
        by_result = {op.result: op for op in (list(p.ast.filters) + list(p.ast.maps))}
        record_returning_functions = {
            fn.name for fn in p.ast.functions
            if getattr(getattr(fn, "return_type", None), "name", None) in records
        }
        cursor = sort_stage.source
        scalar_boundary = None
        while cursor in by_result:
            op = by_result[cursor]
            if isinstance(op, MapOp):
                is_record_map = (
                    isinstance(op.expr, Call)
                    and (op.expr.name in records or op.expr.name in record_returning_functions)
                )
                if not is_record_map:
                    scalar_boundary = op
                    break
            cursor = op.source
        if scalar_boundary is not None:
            record_sources = {}
            for b in p.ast.bindings:
                value = b.expr
                if not (isinstance(value, Literal) and isinstance(value.value, list) and value.value):
                    continue
                rows = value.value
                if not all(isinstance(x, Call) and x.name in records for x in rows):
                    continue
                record_name = rows[0].name
                if any(x.name != record_name for x in rows):
                    continue
                decl = records[record_name]
                def flatten_value(arg, type_name, prefix=""):
                    if type_name.name in {"Number", "Boolean", "Text"}:
                        if not isinstance(arg, Literal):
                            raise ValueError("native Record-to-scalar pipeline requires literal scalar record fields")
                        return {prefix: arg.value}
                    nested = records.get(type_name.name)
                    if nested is None or not isinstance(arg, Call) or arg.name != nested.name:
                        raise ValueError("native Record-to-scalar pipeline requires literal nested Record constructors")
                    if len(arg.args) != len(nested.fields):
                        raise ValueError("native Record-to-scalar pipeline requires valid nested Record constructor arity")
                    out = {}
                    for (child_name, child_type), child_arg in zip(nested.fields, arg.args):
                        child_prefix = f"{prefix}.{child_name}" if prefix else child_name
                        out.update(flatten_value(child_arg, child_type, child_prefix))
                    return out

                table_rows = []
                for row in rows:
                    if len(row.args) != len(decl.fields):
                        raise ValueError("native Record-to-scalar pipeline requires valid record constructor arity")
                    table = {}
                    for (field_name, field_type), arg in zip(decl.fields, row.args):
                        table.update(flatten_value(arg, field_type, field_name))
                    table_rows.append(table)
                record_sources[b.name] = table_rows

            source_name = scalar_boundary.source
            # A logical binding may have several successive in-place filters
            # (`selected = selected where ...`).  The result-name lookup above
            # intentionally keeps the latest operation, but following that
            # self-source edge cannot make progress and used to loop forever.
            # Walk through the earliest non-self producer for such a binding,
            # while tracking visited names to keep malformed/cyclic graphs
            # bounded and diagnosable.
            operations_by_result = {}
            for candidate in list(p.ast.filters) + list(p.ast.maps):
                operations_by_result.setdefault(candidate.result, []).append(candidate)
            visited_sources = set()
            while source_name in by_result and source_name not in visited_sources:
                visited_sources.add(source_name)
                source_op = by_result[source_name]
                if source_op.source == source_name:
                    origin = next(
                        (candidate for candidate in operations_by_result.get(source_name, ())
                         if candidate.source != source_name),
                        None,
                    )
                    if origin is None:
                        break
                    source_op = origin
                source_name = source_op.source
            if source_name in visited_sources and source_name not in record_sources:
                raise ValueError(
                    "native Record-to-scalar sort pipeline contains a cyclic source dependency"
                )
            if source_name not in record_sources:
                raise ValueError("native Record-to-scalar sort pipeline requires a literal Record source")

            lowered = replace(p, data_tables=record_sources)
            lowered.ast.records = []
            lowered.ast.bindings = [b for b in p.ast.bindings if b.name not in record_sources]
            # The record schema contract describes the structured value before
            # the projection boundary. The scalar backend now owns the lowered
            # representation, so do not let the old Record contract force its
            # field typing back into the scalar buffers.
            setattr(lowered, "_backend_schema_contract", ())

            # The generic scalar collection backend represents its numeric
            # columns as f64 buffers. Boolean Record fields used by a pre-map
            # filter therefore become 0/1 numeric columns at this internal
            # boundary. Rewrite the corresponding boolean literals as numeric
            # constants; the public S-Lang type is unchanged. Text fields are
            # deliberately left alone and continue to use the structured
            # Record backend when they are required by a scalar pre-sort filter.
            bool_fields = set()
            for record in p.ast.records:
                for field_name, field_type in record.fields:
                    if getattr(field_type, "name", None) == "Boolean":
                        bool_fields.add(field_name)
            if bool_fields:
                def rewrite_bool_literals(expr):
                    if isinstance(expr, Literal) and isinstance(expr.value, bool):
                        return Literal(1 if expr.value else 0)
                    if isinstance(expr, Binary):
                        return Binary(expr.op, rewrite_bool_literals(expr.left), rewrite_bool_literals(expr.right))
                    if isinstance(expr, Compare):
                        return Compare(expr.op, rewrite_bool_literals(expr.left), rewrite_bool_literals(expr.right))
                    if isinstance(expr, Logical):
                        return Logical(expr.op, rewrite_bool_literals(expr.left), rewrite_bool_literals(expr.right) if expr.right is not None else None)
                    if isinstance(expr, Conditional):
                        return Conditional(rewrite_bool_literals(expr.condition), rewrite_bool_literals(expr.then_expr), rewrite_bool_literals(expr.else_expr))
                    if isinstance(expr, Call):
                        return Call(expr.name, tuple(rewrite_bool_literals(a) for a in expr.args))
                    return expr
                lowered.ast.filters = [
                    mark_source_span(
                        replace(op, predicate=replace(op.predicate, expr=rewrite_bool_literals(op.predicate.expr))),
                        source_span_of(op),
                    )
                    for op in lowered.ast.filters
                ]
                lowered.data_tables = {
                    name: [
                        {k: (1 if v is True else 0 if v is False else v) for k, v in row.items()}
                        for row in rows
                    ]
                    for name, rows in lowered.data_tables.items()
                }
            def _flatten_row_expr(expr):
                def path_of(e):
                    if isinstance(e, Name) and e.name == "row":
                        return ()
                    if isinstance(e, (Field, Property)):
                        base = path_of(e.base)
                        if base is not None:
                            return base + (e.name,)
                    return None
                path = path_of(expr)
                if path is not None and path:
                    return Field(Name("row"), ".".join(path))
                if isinstance(expr, Binary):
                    return Binary(expr.op, _flatten_row_expr(expr.left), _flatten_row_expr(expr.right))
                if isinstance(expr, Compare):
                    return Compare(expr.op, _flatten_row_expr(expr.left), _flatten_row_expr(expr.right))
                if isinstance(expr, Logical):
                    return Logical(expr.op, _flatten_row_expr(expr.left), _flatten_row_expr(expr.right) if expr.right is not None else None)
                if isinstance(expr, Conditional):
                    return Conditional(_flatten_row_expr(expr.condition), _flatten_row_expr(expr.then_expr), _flatten_row_expr(expr.else_expr))
                if isinstance(expr, Call):
                    return Call(expr.name, tuple(_flatten_row_expr(a) for a in expr.args))
                return expr

            lowered.ast.filters = [mark_source_span(replace(op, predicate=replace(op.predicate, expr=_flatten_row_expr(op.predicate.expr))), source_span_of(op)) for op in lowered.ast.filters]
            lowered.ast.maps = [mark_source_span(replace(op, expr=_flatten_row_expr(op.expr)), source_span_of(op)) for op in lowered.ast.maps]
            function_part = None
            signatures = None
            if lowered.ast.functions:
                function_part, signatures = _native_function_llvm_ir(lowered)
            if lowered.ast.maps and len(lowered.ast.maps) == 1 and lowered.ast.sorts:
                # 1.10.89: Text projections cross the same scalar boundary as
                # Number projections, but use a pointer buffer and strcmp.
                def _map_row_path(expr):
                    def rp(e):
                        if isinstance(e, Name) and e.name == "row": return ()
                        if isinstance(e, (Field, Property)):
                            b=rp(e.base)
                            return None if b is None else b+(e.name,)
                        return None
                    q=rp(expr)
                    return ".".join(q) if q else None
                mp=_map_row_path(lowered.ast.maps[0].expr)
                if mp:
                    probe_source = lowered.ast.filters[0].source if lowered.ast.filters else lowered.ast.maps[0].source
                    probe=lowered.data_tables.get(probe_source, [])
                    if probe and isinstance(probe[0].get(mp), str):
                        return _record_filter_scalar_text_sort_llvm_ir(lowered, function_part=function_part, signatures=signatures)
                if mp:
                    probe_source = lowered.ast.filters[0].source if lowered.ast.filters else lowered.ast.maps[0].source
                    probe=lowered.data_tables.get(probe_source, [])
                    if probe and isinstance(probe[0].get(mp), bool):
                        if not lowered.ast.aggregates or any(
                            item.operation not in {'count', 'any', 'all'}
                            for item in lowered.ast.aggregates
                        ):
                            raise ValueError("native Record Boolean scalar bridge supports count, any, and all")
                        lowered.data_tables = {
                            name: [
                                {k: (1 if v is True else 0 if v is False else v) for k, v in row.items()}
                                for row in rows
                            ]
                            for name, rows in lowered.data_tables.items()
                        }
                        return aggregate_llvm_ir(lowered, function_part=function_part, signatures=signatures)
                    if probe and isinstance(probe[0].get(mp), str):
                        return _record_filter_scalar_text_sort_llvm_ir(lowered, function_part=function_part, signatures=signatures)
                if lowered.ast.filters and lowered.ast.maps[0].source in {f.result for f in lowered.ast.filters}:
                    # 1.10.87: keep all numeric Record fields alive through the
                    # filter when the first scalar map depends on more than one
                    # row field.
                    return _record_filter_scalar_sort_llvm_ir(lowered, function_part=function_part, signatures=signatures)
            if lowered.ast.aggregates:
                return aggregate_llvm_ir(lowered, function_part=function_part, signatures=signatures)
            return sort_llvm_ir(lowered, function_part=function_part, signatures=signatures)

    # 1.8.71: once a pipeline contains a stable sort, use the structured sort
    # backend. It preserves whole records while allowing Record -> Record maps
    # before the sort and scalar terminal reductions/aggregates after it.
    if p.ast.sorts:
        return record_collection_sort_llvm_ir(p)

    # 1.8.67: terminal numeric reduce/aggregate over direct record collections.
    # Flatten the record literal into an internal scalar table and reuse the
    # existing numeric terminal backends. The public S-Lang value remains
    # List<Record<T>>; flattening is only a native lowering detail.
    if p.ast.aggregates or p.ast.reduces:
        records = {r.name: r for r in p.ast.records}
        record_sources = {}
        for b in p.ast.bindings:
            v = b.expr
            if not (isinstance(v, Literal) and isinstance(v.value, list) and v.value):
                continue
            xs = v.value
            if not all(isinstance(x, Call) and x.name in records for x in xs):
                continue
            rn = xs[0].name
            if any(x.name != rn for x in xs):
                continue
            decl = records[rn]
            if any(len(x.args) != len(decl.fields) for x in xs):
                raise ValueError("invalid record constructor arity")
            record_sources[b.name] = (rn, xs)

        if record_sources:
            boolean_terminal = False

            def rewrite_expr(expr):
                if isinstance(expr, Property):
                    parts = []
                    current = expr
                    while isinstance(current, Property):
                        parts.append(current.name)
                        current = current.base
                    if isinstance(current, Name) and current.name in {"row", "item"}:
                        # Nested record paths are represented as flattened
                        # scalar columns only inside this native lowering.
                        return Field(Name("row"), "__".join(reversed(parts)))
                    base = rewrite_expr(expr.base)
                    return Property(base, expr.name)
                if isinstance(expr, Field):
                    base = rewrite_expr(expr.base)
                    if isinstance(base, Name) and base.name == "item":
                        base = Name("row")
                    return Field(base, expr.name)
                if isinstance(expr, Literal) and isinstance(expr.value, bool):
                    return Literal(1 if expr.value else 0)
                if isinstance(expr, Binary):
                    return Binary(expr.op, rewrite_expr(expr.left), rewrite_expr(expr.right))
                if isinstance(expr, Compare):
                    return Compare(expr.op, rewrite_expr(expr.left), rewrite_expr(expr.right))
                if isinstance(expr, Logical):
                    return Logical(expr.op, rewrite_expr(expr.left), rewrite_expr(expr.right))
                if isinstance(expr, Call):
                    return Call(expr.name, tuple(rewrite_expr(a) for a in expr.args))
                return expr

            flat_tables = {}

            def flatten_record_value(call, record_name, prefix=(), active=()):
                if record_name in active:
                    raise ValueError("native record terminal operations do not support recursive record types")
                decl = records.get(record_name)
                if decl is None or not isinstance(call, Call) or call.name != record_name:
                    raise ValueError(f"native record terminal operations require a {record_name} constructor")
                if len(call.args) != len(decl.fields):
                    raise ValueError("invalid record constructor arity")
                row = {}
                for idx, (fname, typ) in enumerate(decl.fields):
                    arg = call.args[idx]
                    path = prefix + (fname,)
                    if typ.name in records:
                        row.update(flatten_record_value(arg, typ.name, path, active + (record_name,)))
                        continue
                    if typ.name not in {"Number", "Boolean", "Text"}:
                        raise ValueError(f"unsupported native record terminal field type '{typ.name}'")
                    if not isinstance(arg, Literal):
                        raise ValueError("native record terminal operations require literal scalar fields")
                    value = (1 if arg.value else 0) if isinstance(arg.value, bool) else arg.value
                    row["__".join(path)] = value
                    if len(path) == 1:
                        row[fname] = value
                return row

            for source, (rn, xs) in record_sources.items():
                flat_tables[source] = [flatten_record_value(x, rn) for x in xs]

            lowered = replace(p, data_tables=flat_tables)
            lowered.ast.records = []
            lowered.ast.bindings = [b for b in p.ast.bindings if b.name not in record_sources]
            def preserve_span(original, updated):
                return mark_source_span(updated, source_span_of(original))

            lowered.ast.filters = [
                preserve_span(op, replace(op, predicate=Predicate(rewrite_expr(op.predicate.expr))))
                for op in p.ast.filters
            ]
            lowered.ast.maps = [preserve_span(op, replace(op, expr=rewrite_expr(op.expr))) for op in p.ast.maps]
            lowered.ast.sorts = [
                preserve_span(op, replace(op, spec=SortSpec(rewrite_expr(op.spec.expr), op.spec.ascending)))
                for op in p.ast.sorts
            ]
            lowered.ast.aggregates = [preserve_span(op, replace(op, expr=rewrite_expr(op.expr))) for op in p.ast.aggregates]
            lowered.ast.reduces = [
                preserve_span(op, replace(op, initial=rewrite_expr(op.initial), expr=rewrite_expr(op.expr)))
                for op in p.ast.reduces
            ]
            # A numeric map from a record field produces an ordinary scalar
            # collection, so the normal aggregate/reduce backends can consume it.
            if p.ast.reduces:
                if p.ast.sorts:
                    return pipeline_sort_reduce_llvm_ir(lowered)
                return fused_reduce_llvm_ir(lowered)
            if p.ast.sorts or (p.ast.aggregates and p.ast.aggregates[0].operation in {'any', 'all'}):
                return aggregate_llvm_ir(lowered)
            return fused_aggregate_llvm_ir(lowered)

    # 1.8.62: native nested record paths inside List<Record<T>>.  The compiler
    # flattens only scalar leaves needed by the pipeline into private arrays;
    # the S-Lang model remains a nested Record collection.
    records = {r.name: r for r in p.ast.records}
    def _path(expr):
        parts=[]; cur=expr
        while isinstance(cur, Property):
            parts.append(cur.name); cur=cur.base
        if isinstance(cur, Name) and cur.name in {"row","item"} and parts:
            return tuple(reversed(parts))
        return None
    nested=[]
    for op in list(p.ast.filters)+list(p.ast.maps)+list(p.ast.sorts)+list(p.ast.aggregates)+list(p.ast.reduces):
        if isinstance(op, FilterOp): expr=op.predicate.expr
        elif isinstance(op, SortOp): expr=op.spec.expr
        elif isinstance(op, AggregateOp): expr=op.expr
        elif isinstance(op, ReduceOp): expr=op.expr
        else: expr=op.expr
        _validate_expr_fields(expr, op.source)
        stack=[expr]
        while stack:
            x=stack.pop()
            q=_path(x) if isinstance(x,Property) else None
            if q and len(q)>1: nested.append(q)
            if isinstance(x,Property): stack.append(x.base)
            elif isinstance(x,(Binary,Compare,Logical)):
                for a in ("left","right"):
                    y=getattr(x,a,None)
                    if y is not None: stack.append(y)
    if nested:
        if any(isinstance(op.expr, Call) and op.expr.name in records for op in p.ast.maps):
            if p.ast.filters or p.ast.sorts or p.ast.aggregates or p.ast.reduces or p.ast.functions:
                raise ValueError("native nested record constructor maps currently support map stages only")
            return _nested_record_constructor_collection_llvm_ir(p, records)

        # 1.8.64: flatten read-only nested scalar paths for the existing numeric
        # pipeline backend. This keeps sort/reduce/aggregate implementation
        # shared: nested records remain the public S-Lang type, while the
        # lowering exposes only the scalar leaves actually referenced by the
        # pipeline.
        if p.ast.sorts or p.ast.aggregates or p.ast.reduces:
            sources={}
            for b in p.ast.bindings:
                if not (isinstance(b.expr,Literal) and isinstance(b.expr.value,list) and b.expr.value):
                    continue
                xs=b.expr.value
                if not all(isinstance(x,Call) and x.name in records for x in xs): continue
                rn=xs[0].name
                if any(x.name!=rn for x in xs): continue
                sources[b.name]=(rn,xs)
            if not sources:
                raise ValueError("native nested record pipeline requires a record-list literal source")

            def flatten_value(call, rn, prefix, out):
                decl=records[rn]
                for idx,(fname,typ) in enumerate(decl.fields):
                    arg=call.args[idx]
                    path=prefix+(fname,)
                    if typ.name in records and isinstance(arg,Call) and arg.name==typ.name:
                        flatten_value(arg,typ.name,path,out)
                    elif typ.name in {"Number","Boolean","Text"}:
                        out["__".join(path)] = arg.value if isinstance(arg,Literal) else None

            flat_tables={}
            for name,(rn,xs) in sources.items():
                rows=[]
                for x in xs:
                    row={}; flatten_value(x,rn,(),row); rows.append(row)
                flat_tables[name]=rows

            def rewrite_nested(expr):
                if isinstance(expr,Property):
                    parts=[]; cur=expr
                    while isinstance(cur,Property):
                        parts.append(cur.name); cur=cur.base
                    if isinstance(cur,Name) and cur.name in {"row","item"}:
                        return Field(Name(cur.name),"__".join(reversed(parts)))
                    return Property(rewrite_nested(cur),expr.name)
                if isinstance(expr,Binary):
                    return Binary(expr.op,rewrite_nested(expr.left),rewrite_nested(expr.right))
                if isinstance(expr,Compare):
                    return Compare(expr.op,rewrite_nested(expr.left),rewrite_nested(expr.right))
                if isinstance(expr,Logical):
                    return Logical(expr.op,rewrite_nested(expr.left),rewrite_nested(expr.right))
                if isinstance(expr,Call):
                    return Call(expr.name,tuple(rewrite_nested(a) for a in expr.args))
                return expr

            def rewrite_op(op):
                if isinstance(op,FilterOp):
                    return replace(op,predicate=Predicate(rewrite_nested(op.predicate.expr)))
                if isinstance(op,MapOp):
                    return replace(op,expr=rewrite_nested(op.expr))
                if isinstance(op,SortOp):
                    return replace(op,spec=SortSpec(rewrite_nested(op.spec.expr),op.spec.ascending))
                if isinstance(op,AggregateOp):
                    return replace(op,expr=rewrite_nested(op.expr))
                if isinstance(op,ReduceOp):
                    return replace(op,initial=rewrite_nested(op.initial),expr=rewrite_nested(op.expr))
                return op

            lowered=replace(p,data_tables=flat_tables)
            # The flattened table is an internal compiler view; remove the
            # source record literal from semantic validation and expose it as
            # an ordinary Row table with synthetic scalar fields.
            lowered.ast.records=[]
            lowered.ast.bindings=[b for b in p.ast.bindings if not (isinstance(b.expr,Literal) and isinstance(b.expr.value,list))]
            lowered.ast.filters=[rewrite_op(x) for x in p.ast.filters]
            lowered.ast.maps=[rewrite_op(x) for x in p.ast.maps]
            lowered.ast.sorts=[rewrite_op(x) for x in p.ast.sorts]
            lowered.ast.aggregates=[rewrite_op(x) for x in p.ast.aggregates]
            lowered.ast.reduces=[rewrite_op(x) for x in p.ast.reduces]
            if p.ast.sorts and p.ast.reduces:
                return pipeline_sort_reduce_llvm_ir(lowered)
            if p.ast.reduces:
                return reduce_llvm_ir(lowered)
            if p.ast.aggregates:
                return aggregate_llvm_ir(lowered)
            if p.ast.sorts:
                return sort_llvm_ir(lowered)
        sources={}
        for b in p.ast.bindings:
            v=b.expr
            if not (isinstance(v,Literal) and isinstance(v.value,list) and v.value): continue
            xs=v.value
            if not all(isinstance(x,Call) and x.name in records for x in xs): continue
            rn=xs[0].name
            if any(x.name!=rn for x in xs): continue
            sources[b.name]=(rn,xs)
        if not sources: raise ValueError("native nested record collection requires a record-list literal source")
        rname,rows=next(iter(sources.values()))
        def resolve(rn,path):
            cur=rn
            for i,part in enumerate(path):
                decl=records[cur]
                found=next(((j,t) for j,(n,t) in enumerate(decl.fields) if n==part),None)
                if found is None: raise ValueError(f"unknown nested record field '{cur}.{part}'")
                _,t=found
                if i==len(path)-1: return t.name
                if t.name not in records: raise ValueError(f"field '{cur}.{part}' is not a record")
                cur=t.name
        def value_at(call,path):
            cur=call; curtype=rname
            for i,part in enumerate(path):
                decl=records[curtype]
                idx=next((j for j,(n,_) in enumerate(decl.fields) if n==part),None)
                if idx is None: raise ValueError(f"unknown nested record field '{curtype}.{part}'")
                arg=cur.args[idx]
                if i==len(path)-1: return arg
                if not (isinstance(arg,Call) and arg.name in records): raise ValueError("native nested record collection requires literal nested records")
                cur=arg; curtype=arg.name
        leaf_types={q:resolve(rname,q) for q in set(nested)}
        if any(t not in {"Number","Boolean","Text"} for t in leaf_types.values()): raise ValueError("nested record paths must resolve to scalar fields")
        lines=["; ModuleID = 'slang-nested-record-collections'",'source_filename = "slang"','']
        data={}
        for q,t in leaf_types.items():
            vals=[value_at(x,q) for x in rows]; key='_'.join(q)
            g=f"@nrc_{key}"
            if t=="Number":
                if not all(isinstance(a,Literal) and isinstance(a.value,(int,float)) and not isinstance(a.value,bool) for a in vals): raise ValueError("nested numeric fields must be literals")
                lines.append(f"{g} = private constant [{len(vals)} x double] [{', '.join('double '+format(float(a.value),'.17e') for a in vals)}]")
            elif t=="Boolean":
                if not all(isinstance(a,Literal) and isinstance(a.value,bool) for a in vals): raise ValueError("nested Boolean fields must be literals")
                lines.append(f"{g} = private constant [{len(vals)} x i1] [{', '.join('i1 1' if a.value else 'i1 0' for a in vals)}]")
            else:
                ptrs=[]
                for j,a in enumerate(vals):
                    if not isinstance(a,Literal) or not isinstance(a.value,str): raise ValueError("nested Text fields must be literals")
                    k=f"nrc_text_{key}_{j}"; enc,l=_llvm_c_string(a.value); lines.append(f'@{k} = private constant [{l} x i8] c"{enc}"'); ptrs.append(f"ptr getelementptr inbounds ([{l} x i8], ptr @{k}, i64 0, i64 0)")
                lines.append(f"{g} = private constant [{len(vals)} x ptr] [{', '.join(ptrs)}]")
            data[q]=(g,len(vals),t)
        lines += ['', 'declare i32 @printf(ptr, ...)', '@nrc_fmt = private constant [7 x i8] c"%.15g\\0A\\00"', 'define i32 @main() {', 'entry:']
        desc={}; current='entry'; count0=len(rows)
        def load(q,serial):
            g,n,t=data[q]; llvm={'Number':'double','Boolean':'i1','Text':'ptr'}[t]; ptr=f"%nrc_p_{serial}_{len(lines)}"; val=f"%nrc_v_{serial}_{len(lines)+1}"
            lines.append(f"  {ptr} = getelementptr inbounds [{n} x {llvm}], ptr {g}, i64 0, i64 %nrc_i_{serial}"); lines.append(f"  {val} = load {llvm}, ptr {ptr}"); return t,val
        def exprval(e,serial):
            q=_path(e) if isinstance(e,Property) else None
            if q in data: return load(q,serial)
            if isinstance(e,Literal) and isinstance(e.value,(int,float)) and not isinstance(e.value,bool): return 'Number',format(float(e.value),'.17e')
            if isinstance(e,Literal) and isinstance(e.value,bool): return 'Boolean','1' if e.value else '0'
            if isinstance(e,Binary) and e.op in {'+','-','*','/'}:
                a,av=exprval(e.left,serial); b,bv=exprval(e.right,serial)
                if a!='Number' or b!='Number': raise ValueError("nested arithmetic requires Number")
                n=f"%nrc_e_{serial}_{len(lines)}"; opmap={"+":"fadd","-":"fsub","*":"fmul","/":"fdiv"}; lines.append(f"  {n} = {opmap[e.op]} double {av}, {bv}"); return "Number",n
            raise ValueError("native nested record expression is unsupported")
        def predicate(e,serial):
            if isinstance(e,Logical):
                if e.op=='not':
                    a=predicate(e.left,serial); n=f"%nrc_not_{serial}_{len(lines)}"; lines.append(f"  {n} = xor i1 {a}, true"); return n
                a=predicate(e.left,serial); b=predicate(e.right,serial); n=f"%nrc_log_{serial}_{len(lines)}"; lines.append(f"  {n} = {e.op} i1 {a}, {b}"); return n
            if not isinstance(e,Compare): raise ValueError("nested filter requires comparison")
            a,av=exprval(e.left,serial); b,bv=exprval(e.right,serial)
            n=f"%nrc_c_{serial}_{len(lines)}"
            if a!='Number' or b!='Number': raise ValueError("native nested filter currently compares Number values")
            pm={'>':'ogt','>=':'oge','<':'olt','<=':'ole','==':'oeq','!=':'one'}; lines.append(f"  {n} = fcmp {pm[e.op]} double {av}, {bv}"); return n
        ops=list(p.ast.filters)+list(p.ast.maps)
        for serial,op in enumerate(ops,1):
            if op.source not in desc and op.source not in sources: raise ValueError("nested collection pipeline must be forward and acyclic")
            if op.source in desc: srcdesc=desc[op.source]; count=srcdesc[1]; srcmap=srcdesc[0]
            else: count=count0; srcmap=None
            limit=count
            if isinstance(count,str):
                limit=f"%nrc_countval_{serial}"; lines.append(f"  {limit} = load i64, ptr {count}")
            if isinstance(op,FilterOp):
                bufs={}; cap=count0 if isinstance(count,int) else count0
                for q,t in leaf_types.items():
                    llvm={'Number':'double','Boolean':'i1','Text':'ptr'}[t]; bufs[q]=f"%nrc_buf_{serial}_{'_'.join(q)}"; lines.append(f"  {bufs[q]} = alloca [{cap} x {llvm}]")
                cnt=f"%nrc_cnt_{serial}"; lines += [f"  {cnt} = alloca i64",f"  store i64 0, ptr {cnt}",f"  br label %nrc_loop_{serial}",f"nrc_loop_{serial}:",f"  %nrc_i_{serial} = phi i64 [ 0, %{current} ], [ %nrc_next_{serial}, %nrc_skip_{serial} ]",f"  %nrc_has_{serial} = icmp ult i64 %nrc_i_{serial}, {limit}",f"  br i1 %nrc_has_{serial}, label %nrc_body_{serial}, label %nrc_done_{serial}",f"nrc_body_{serial}:"]
                keep=predicate(op.predicate.expr,serial); lines += [f"  br i1 {keep}, label %nrc_keep_{serial}, label %nrc_skip_{serial}",f"nrc_keep_{serial}:",f"  %nrc_o_{serial} = load i64, ptr {cnt}"]
                for q,t in leaf_types.items():
                    llvm={'Number':'double','Boolean':'i1','Text':'ptr'}[t]; sg=data[q][0] if op.source in sources else srcmap[q]
                    sp=f"%nrc_sp_{serial}_{'_'.join(q)}"; sv=f"%nrc_sv_{serial}_{'_'.join(q)}"; dp=f"%nrc_dp_{serial}_{'_'.join(q)}"
                    lines += [f"  {sp} = getelementptr inbounds [{count0} x {llvm}], ptr {sg}, i64 0, i64 %nrc_i_{serial}",f"  {sv} = load {llvm}, ptr {sp}",f"  {dp} = getelementptr [{cap} x {llvm}], ptr {bufs[q]}, i64 0, i64 %nrc_o_{serial}",f"  store {llvm} {sv}, ptr {dp}"]
                lines += [f"  %nrc_inc_{serial} = add i64 %nrc_o_{serial}, 1",f"  store i64 %nrc_inc_{serial}, ptr {cnt}",f"  br label %nrc_skip_{serial}",f"nrc_skip_{serial}:",f"  %nrc_next_{serial} = add i64 %nrc_i_{serial}, 1",f"  br label %nrc_loop_{serial}",f"nrc_done_{serial}:"]
                desc[op.result]=(bufs,cnt); current=f"nrc_done_{serial}"
            else:
                q=_path(op.expr) if isinstance(op.expr,Property) else None
                if q not in data or leaf_types[q] != 'Number': raise ValueError("native nested record map currently projects a numeric nested field")
                out=f"%nrc_map_{serial}"; cap=count0; lines.append(f"  {out} = alloca [{cap} x double]")
                loop=f"nrc_mloop_{serial}"; body=f"nrc_mbody_{serial}"; done=f"nrc_mdone_{serial}"; lines += [f"  br label %{loop}",f"{loop}:",f"  %nrc_i_{serial} = phi i64 [ 0, %{current} ], [ %nrc_next_{serial}, %{body} ]",f"  %nrc_has_{serial} = icmp ult i64 %nrc_i_{serial}, {limit}",f"  br i1 %nrc_has_{serial}, label %{body}, label %{done}",f"{body}:"]
                if op.source in sources: sg=data[q][0]
                else: sg=srcmap[q]
                llvm='double'; sp=f"%nrc_msp_{serial}"; sv=f"%nrc_msv_{serial}"; dp=f"%nrc_mdp_{serial}"; lines += [f"  {sp} = getelementptr inbounds [{count0 if op.source in sources else cap} x double], ptr {sg}, i64 0, i64 %nrc_i_{serial}",f"  {sv} = load double, ptr {sp}",f"  {dp} = getelementptr [{cap} x double], ptr {out}, i64 0, i64 %nrc_i_{serial}",f"  store double {sv}, ptr {dp}",f"  %nrc_next_{serial} = add i64 %nrc_i_{serial}, 1",f"  br label %{loop}",f"{done}:"]
                desc[op.result]=(out,count); current=done
        for j,(name,d) in enumerate(desc.items()):
            if not any(isinstance(x,Name) and x.name==name for x in p.show_exprs): continue
            ptr,cnt=d
            if isinstance(ptr,dict): raise ValueError("show requires a scalar nested-field map result")
            loop=f"nrc_show_{j}"; body=f"nrc_showb_{j}"; done=f"nrc_showd_{j}"; lines += [f"  br label %{loop}",f"{loop}:",f"  %nrc_si_{j} = phi i64 [ 0, %{current} ], [ %nrc_sn_{j}, %{body} ]",f"  %nrc_sc_{j} = load i64, ptr {cnt}" if isinstance(cnt,str) else f"  %nrc_sc_{j} = add i64 0, {cnt}",f"  %nrc_sx_{j} = icmp ult i64 %nrc_si_{j}, %nrc_sc_{j}",f"  br i1 %nrc_sx_{j}, label %{body}, label %{done}",f"{body}:",f"  %nrc_sp_{j} = getelementptr double, ptr {ptr}, i64 %nrc_si_{j}",f"  %nrc_sv_{j} = load double, ptr %nrc_sp_{j}",f"  call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([7 x i8], ptr @nrc_fmt, i64 0, i64 0), double %nrc_sv_{j})",f"  %nrc_sn_{j} = add i64 %nrc_si_{j}, 1",f"  br label %{loop}",f"{done}:"]
            current=done
        lines += ['  ret i32 0','}','']
        return '\n'.join(lines)

    # Once a record collection has projected a numeric field, the ordinary
    # numeric pipeline backend can execute the remaining sort/reduce/aggregate
    # stages. Build a semantic data-table view of record-list literals; this is
    # an internal compiler representation and does not change the S-Lang type.
    if p.ast.sorts or p.ast.aggregates or p.ast.reduces:
        record_tables = {}
        records = {r.name: r for r in p.ast.records}
        for b in p.ast.bindings:
            if not (isinstance(b.expr, Literal) and isinstance(b.expr.value, list) and b.expr.value):
                continue
            xs = b.expr.value
            if not all(isinstance(x, Call) and x.name in records for x in xs):
                continue
            rn = xs[0].name
            if any(x.name != rn for x in xs):
                continue
            decl = records[rn]
            if any(len(x.args) != len(decl.fields) for x in xs):
                continue
            rows = []
            for x in xs:
                row = {}
                for (fname, _typ), arg in zip(decl.fields, x.args):
                    if not isinstance(arg, Literal):
                        raise ValueError("native record pipeline requires literal record fields")
                    row[fname] = arg.value
                rows.append(row)
            record_tables[b.name] = rows
        if not record_tables:
            raise ValueError("native record pipeline requires a record-list literal source")
        lowered = replace(p, data_tables=record_tables)
        if p.ast.sorts and p.ast.reduces:
            return pipeline_sort_reduce_llvm_ir(lowered)
        if p.ast.reduces:
            return reduce_llvm_ir(lowered)
        if p.ast.aggregates:
            return aggregate_llvm_ir(lowered)
        if p.ast.sorts:
            return sort_llvm_ir(lowered)
    if not p.ast.records or not p.ast.filters and not p.ast.maps:
        raise ValueError("not a record collection program")
    if p.ast.sorts or p.ast.aggregates or p.ast.reduces:
        raise ValueError("native record collections currently support where/map only")
    records={r.name:r for r in p.ast.records}
    sources={}
    for b in p.ast.bindings:
        if not (isinstance(b.expr, Literal) and isinstance(b.expr.value,list) and b.expr.value): continue
        xs=b.expr.value
        if not all(isinstance(x,Call) and x.name in records for x in xs): continue
        rn=xs[0].name
        if any(x.name!=rn for x in xs): raise ValueError("record collection must contain one record type")
        decl=records[rn]
        if any(len(x.args)!=len(decl.fields) for x in xs): raise ValueError("invalid record constructor arity")
        sources[b.name]=(rn,xs)
    if not sources: raise ValueError("not a record collection program")
    ordered=[]; avail=set(sources); rem=list(p.ast.filters)+list(p.ast.maps)
    while rem:
        progress=False
        for op in rem[:]:
            if op.source in avail:
                ordered.append(op); avail.add(op.result); rem.remove(op); progress=True
        if not progress: raise ValueError("record collection pipeline must be forward and acyclic")
    rname=next(iter(sources.values()))[0]; decl=records[rname]
    # 1.10.39: intermediate record stages use the semantic output schema as the authoritative storage contract.
    # Keep AST declarations only for record-constructor values; lowering uses
    # the semantic schema for field order, names and scalar storage types.
    schema_by_binding = {}
    for binding, in_schema, out_schema in (schema_contract or getattr(p, "_backend_schema_contract", ())):
        schema_by_binding[binding] = (in_schema, out_schema)
    def _contract_fields(binding):
        pair=schema_by_binding.get(binding)
        if pair is None:
            matches=[v for k,v in schema_by_binding.items() if k.split("#",1)[0]==binding]
            if len(matches)==1: pair=matches[0]
        schema=pair[1] if pair else None
        if schema is None: return None
        return tuple((f.name, f.type_name) for f in getattr(schema, "fields", ()))
    source_schema_fields={}
    for source,(rn,xs) in sources.items():
        sf=_contract_fields(source)
        if sf is not None:
            ast_fields=tuple((n,t.name) for n,t in records[rn].fields)
            if sf != ast_fields:
                raise ValueError(f"native backend schema contract for '{source}' does not match source record storage layout")
            source_schema_fields[source]=sf
    schema_fields_for_root=source_schema_fields.get(next(iter(sources)), tuple((n,t.name) for n,t in decl.fields))
    ftypes=dict(schema_fields_for_root); findex={n:i for i,(n,_) in enumerate(schema_fields_for_root)}
    if any(t not in {"Number","Boolean","Text"} for t in ftypes.values()): raise ValueError("record collection fields must be Number, Boolean, or Text")

    # 1.8.68: typed user functions may consume the current Record row.
    # Records are flattened only at the LLVM ABI boundary; S-Lang still sees
    # one Record parameter. This keeps field access explicit and auditable.
    fn_sigs = {}
    fn_blocks = []
    fn_counter = [0]
    def fn_fresh(prefix):
        v=f"{prefix}_{fn_counter[0]}"; fn_counter[0]+=1; return v
    def fn_llvm_type(t, record_name=None):
        if t == "Number": return "double"
        if t == "Boolean": return "i1"
        if t == "Text": return "ptr"
        if t == "Record":
            rn = record_name or rname
            rd = records.get(rn)
            if rd is None: raise ValueError(f"unknown native record type '{rn}'")
            return "ptr"
        raise ValueError(f"unsupported native record function type {t}")
    for fn in p.ast.functions:
        if fn.type_params:
            raise ValueError(f"native record function backend does not yet lower generic function '{fn.name}'")
        public_params=[]; llvm_params=[]
        for pname, pref in fn.parameters:
            rt=_resolve_decl_type(pref, {r.name for r in p.ast.records}, set()) if pref is not None else None
            if rt is not None and rt.name == 'Record' and rt.args and rt.args[0].name in records:
                record_name=rt.args[0].name
                rd=records[record_name]
                fields=[]
                for fname,ft in rd.fields:
                    if ft.name not in {"Number","Boolean","Text"}:
                        raise ValueError("native record function Record parameters currently support Number/Boolean/Text fields")
                    fields.append((fname,ft.name))
                    llvm_params.append(fn_llvm_type(ft.name))
                public_params.append(("record",pname,fields))
            else:
                if rt is None or rt.name not in {"Number","Boolean","Text"}:
                    raise ValueError("native record function backend supports Record, Number, Boolean, and Text parameters")
                public_params.append(("scalar",pname,rt.name)); llvm_params.append(fn_llvm_type(rt.name))
        rr=_resolve_decl_type(fn.return_type, {r.name for r in p.ast.records}, set()) if fn.return_type else None
        if rr is None:
            raise ValueError("native record function backend requires an explicit return type")
        if rr.name not in {"Number","Boolean","Record"}:
            raise ValueError("native record function backend supports Number/Boolean/Record return values")
        result_record = None
        if rr.name == "Record":
            if not rr.args or rr.args[0].name not in records:
                raise ValueError("native record function Record return requires a declared record type")
            result_record = rr.args[0].name
            rd = records[result_record]
            for _, ft in rd.fields:
                if ft.name not in {"Number","Boolean","Text"}:
                    raise ValueError("native Record returns support Number/Boolean/Text fields")
        fn_sigs[fn.name]=(public_params, rr.name if rr.name != "Record" else "Record", tuple(llvm_params), result_record)
    def materialize_record_expr(expr, env, lines):
        if isinstance(expr, Name) and expr.name in env:
            v = env[expr.name]
            if isinstance(v, tuple) and len(v) == 3 and v[0] == "Record":
                return v[1], dict(v[2])
        if isinstance(expr, Call) and expr.name in fn_sigs and fn_sigs[expr.name][1] == "Record":
            public_params, _, _, result_record = fn_sigs[expr.name]
            if len(public_params) != len(expr.args):
                raise ValueError(f"native record function call '{expr.name}' argument count mismatch")
            out_ptrs = {}
            for fname, ft in records[result_record].fields:
                llvm_t = fn_llvm_type(ft.name)
                ptr = f"%{fn_fresh('fret')}_{fname}"
                lines.append(f"  {ptr} = alloca {llvm_t}")
                out_ptrs[fname] = (ft.name, ptr)
            call_args=[]
            for (kind, pname, fields), arg in zip(public_params, expr.args):
                if kind == "record":
                    rn, vals = materialize_record_expr(arg, env, lines)
                    expected = dict(fields)
                    if set(vals) != set(expected) or any(vals[f][0] != expected[f] for f in expected):
                        raise ValueError(f"native record function call '{expr.name}' Record argument type mismatch")
                    for fname, ft in fields:
                        call_args.append(
                            f"{fn_llvm_type(ft.name if hasattr(ft, 'name') else ft)} {vals[fname][1]}"
                        )
                else:
                    at,av=emit_fn_expr(arg,env,lines)
                    if at != fields:
                        raise ValueError(f"native record function call '{expr.name}' argument type mismatch")
                    call_args.append(f"{fn_llvm_type(at)} {av}")
            outs=[f"ptr {out_ptrs[f][1]}" for f,_ in records[result_record].fields]
            lines.append(f"  call void @{expr.name}({', '.join(outs + call_args)})")
            values={}
            for fname, ft in records[result_record].fields:
                llvm_t=fn_llvm_type(ft.name)
                vv=f"%{fn_fresh('fload')}_{fname}"
                lines.append(f"  {vv} = load {llvm_t}, ptr {out_ptrs[fname][1]}")
                values[fname]=(ft.name, vv)
            return result_record, values
        raise ValueError(f"native record expression '{type(expr).__name__}' is not a record value")

    def emit_fn_expr(expr, env, lines):
        if isinstance(expr, Literal):
            if isinstance(expr.value,bool): return "Boolean", "1" if expr.value else "0"
            if isinstance(expr.value,(int,float)) and not isinstance(expr.value,bool): return "Number", f"{float(expr.value):.17e}"
            raise ValueError("native record function backend supports only Number/Boolean literals")
        if isinstance(expr, Name):
            if expr.name not in env: raise ValueError(f"unknown native function value '{expr.name}'")
            return env[expr.name]
        if isinstance(expr,(Field,Property)):
            if isinstance(expr.base,Name):
                key=(expr.base.name,expr.name)
                if key in env and not (isinstance(env[key], tuple) and len(env[key]) == 3 and env[key][0] == "Record"):
                    return env[key]
                if expr.base.name in env and isinstance(env[expr.base.name], tuple) and len(env[expr.base.name]) == 3 and env[expr.base.name][0] == "Record":
                    fields = env[expr.base.name][2]
                    if expr.name in fields:
                        return fields[expr.name]
                raise ValueError(f"native record function cannot resolve field '{expr.base.name}.{expr.name}'")
            if isinstance(expr.base, Call) and expr.base.name in fn_sigs and fn_sigs[expr.base.name][1] == "Record":
                _, fields = materialize_record_expr(expr.base, env, lines)
                if expr.name not in fields:
                    raise ValueError(f"native record function result has no field '{expr.name}'")
                return fields[expr.name]
            raise ValueError(f"native record function cannot resolve field expression '{type(expr.base).__name__}.{expr.name}'")
        if isinstance(expr,Binary) and expr.op in {"+","-","*","/","%"}:
            at,av=emit_fn_expr(expr.left,env,lines); bt,bv=emit_fn_expr(expr.right,env,lines)
            if at!="Number" or bt!="Number": raise ValueError("native record function arithmetic requires Number")
            op={"+":"fadd","-":"fsub","*":"fmul","/":"fdiv","%":"frem"}[expr.op]; n=f"%{fn_fresh('fexpr')}"; lines.append(f"  {n} = {op} double {av}, {bv}"); return "Number",n
        if isinstance(expr,Compare) and expr.op in {">",">=","<","<=","==","!="}:
            at,av=emit_fn_expr(expr.left,env,lines); bt,bv=emit_fn_expr(expr.right,env,lines)
            if at!=bt: raise ValueError("native record function comparison requires matching types")
            n=f"%{fn_fresh('fcmp')}"
            if at=="Number":
                fpred={'>':'ogt','>=':'oge','<':'olt','<=':'ole','==':'oeq','!=':'one'}[expr.op]
                lines.append(f"  {n} = fcmp {fpred} double {av}, {bv}")
            elif at=="Boolean":
                if expr.op not in {"==","!="}: raise ValueError("Boolean comparison supports == and != only")
                ipred={'==':'eq','!=':'ne'}[expr.op]
                lines.append(f"  {n} = icmp {ipred} i1 {av}, {bv}")
            else: raise ValueError("unsupported native record function comparison")
            return "Boolean",n
        if isinstance(expr,Logical):
            if expr.op=="not":
                t,v=emit_fn_expr(expr.left,env,lines);
                if t!="Boolean": raise ValueError("not requires Boolean")
                n=f"%{fn_fresh('fnot')}"; lines.append(f"  {n} = xor i1 {v}, true"); return "Boolean",n
            at,av=emit_fn_expr(expr.left,env,lines); bt,bv=emit_fn_expr(expr.right,env,lines)
            if at!="Boolean" or bt!="Boolean": raise ValueError("logical operators require Boolean")
            n=f"%{fn_fresh('flogic')}"; lines.append(f"  {n} = {'and' if expr.op=='and' else 'or'} i1 {av}, {bv}"); return "Boolean",n
        if isinstance(expr,Conditional):
            ct,cv=emit_fn_expr(expr.condition,env,lines)
            if ct!="Boolean": raise ValueError("conditional expression requires Boolean condition")
            tt,tv=emit_fn_expr(expr.then_expr,env,lines); et,ev=emit_fn_expr(expr.else_expr,env,lines)
            if tt!=et or tt not in {"Number","Boolean"}:
                raise ValueError("native record function conditional branches must have the same scalar type")
            n=f"%{fn_fresh('fselect')}"
            llvm_t=fn_llvm_type(tt)
            lines.append(f"  {n} = select i1 {cv}, {llvm_t} {tv}, {llvm_t} {ev}")
            return tt,n
        if isinstance(expr,Call) and expr.name in fn_sigs:
            public_params,result,result_record = fn_sigs[expr.name][0], fn_sigs[expr.name][1], fn_sigs[expr.name][3]
            if result not in {"Number","Boolean"}:
                raise ValueError(f"native record function cannot call record-returning function '{expr.name}' inside a scalar expression")
            if len(public_params)!=len(expr.args):
                raise ValueError(f"native record function call '{expr.name}' argument count mismatch")
            call_args=[]
            for (kind,pname,fields),arg in zip(public_params,expr.args):
                if kind!="scalar":
                    raise ValueError(f"native record function call '{expr.name}' cannot pass Record arguments in a scalar expression")
                at,av=emit_fn_expr(arg,env,lines)
                if at!=fields: raise ValueError(f"native record function call '{expr.name}' argument type mismatch")
                call_args.append(f"{fn_llvm_type(at)} {av}")
            n=f"%{fn_fresh('fcall')}"
            lines.append(f"  {n} = call {fn_llvm_type(result)} @{expr.name}({', '.join(call_args)})")
            return result,n
        raise ValueError(f"native record function backend does not support expression {type(expr).__name__}")
    for fn in p.ast.functions:
        public_params,result,llvm_params,result_record=fn_sigs[fn.name]
        args=[]; env={}
        k=0
        for kind,pname,fields in public_params:
            if kind=="record":
                record_fields={}
                for fname,ft in fields:
                    llvm_t=fn_llvm_type(ft); an=f"%{pname}_{fname}"; args.append(f"{llvm_t} {an}"); env[(pname,fname)]=(ft,an); record_fields[fname]=(ft,an); k+=1
                record_name = next((rn for rn,rd in records.items() if tuple((f,t.name) for f,t in rd.fields)==tuple(fields)), None)
                env[pname]=("Record", record_name, record_fields)
            else:
                ft=fields; llvm_t=fn_llvm_type(ft); an=f"%{pname}"; args.append(f"{llvm_t} {an}"); env[pname]=(ft,an); k+=1
        if result == "Record":
            args = [f"ptr %result_out_{fname}" for fname,_ in records[result_record].fields] + args
            lines_fn=[f"define void @{fn.name}({', '.join(args)}) {{","entry:"]
        else:
            lines_fn=[f"define {fn_llvm_type(result)} @{fn.name}({', '.join(args)}) {{","entry:"]
        terminated=False
        for stmt in fn.body:
            if isinstance(stmt,ReturnOp):
                if result == "Record":
                    expr = stmt.expr
                    if isinstance(expr, Call) and expr.name == result_record:
                        rd = records[result_record]
                        if len(expr.args) != len(rd.fields):
                            raise ValueError(f"native record function '{fn.name}' return constructor arity mismatch")
                        vals=[]
                        for (fname,ft),arg in zip(rd.fields, expr.args):
                            typ,val=emit_fn_expr(arg,env,lines_fn)
                            if typ != ft.name:
                                raise ValueError(f"native record function '{fn.name}' return field '{fname}' type mismatch")
                            vals.append((ft.name,val))
                    elif isinstance(expr, Call) and expr.name in fn_sigs and fn_sigs[expr.name][1] == "Record":
                        returned_name, returned_fields = materialize_record_expr(expr, env, lines_fn)
                        if returned_name != result_record:
                            raise ValueError(f"native record function '{fn.name}' cannot return {returned_name} as {result_record}")
                        vals=[(ft.name, returned_fields[f][1]) for f,ft in rd.fields]
                    else:
                        raise ValueError(f"native record function '{fn.name}' must return a {result_record} constructor or compatible record call")
                    for idx,(ft,val) in enumerate(vals):
                        lines_fn.append(f"  store {fn_llvm_type(ft)} {val}, ptr %result_out_{rd.fields[idx][0]}")
                    lines_fn.append("  ret void")
                    terminated=True; break
                typ,val=emit_fn_expr(stmt.expr,env,lines_fn)
                if typ!=result: raise ValueError(f"native record function '{fn.name}' return type mismatch")
                lines_fn.append(f"  ret {fn_llvm_type(result)} {val}"); terminated=True; break
            elif isinstance(stmt,LetOp):
                typ,val=emit_fn_expr(stmt.expr,env,lines_fn); env[stmt.name]=(typ,val)
            elif isinstance(stmt,IfOp):
                # 1.10.30: support branch-local control flow in native typed
                # record functions. Branches must return on both sides; this
                # preserves the total-function contract without introducing
                # mutable SSA variables or hidden runtime state.
                ct,cv=emit_fn_expr(stmt.condition,env,lines_fn)
                if ct!="Boolean": raise ValueError(f"native record function '{fn.name}' if condition must be Boolean")
                if not stmt.then_body or not stmt.else_body:
                    raise ValueError(f"native record function '{fn.name}' requires else branch in native if")
                then_label=f"fn_then_{fn_fresh('if')}"; else_label=f"fn_else_{fn_fresh('if')}"
                lines_fn.append(f"  br i1 {cv}, label %{then_label}, label %{else_label}")
                for label,branch in ((then_label,stmt.then_body),(else_label,stmt.else_body)):
                    lines_fn.append(f"{label}:")
                    branch_terminated=False
                    branch_env=dict(env)
                    for inner in branch:
                        if isinstance(inner,LetOp):
                            typ,val=emit_fn_expr(inner.expr,branch_env,lines_fn); branch_env[inner.name]=(typ,val)
                        elif isinstance(inner,ReturnOp):
                            if result=="Record":
                                expr=inner.expr
                                rd=records[result_record]
                                if isinstance(expr,Call) and expr.name==result_record:
                                    if len(expr.args)!=len(rd.fields): raise ValueError(f"native record function '{fn.name}' return constructor arity mismatch")
                                    vals=[]
                                    for (fname,ft),arg in zip(rd.fields,expr.args):
                                        typ,val=emit_fn_expr(arg,branch_env,lines_fn)
                                        if typ!=ft.name: raise ValueError(f"native record function '{fn.name}' return field '{fname}' type mismatch")
                                        vals.append(val)
                                elif isinstance(expr,Call) and expr.name in fn_sigs and fn_sigs[expr.name][1]=="Record":
                                    returned_name, returned_fields=materialize_record_expr(expr,branch_env,lines_fn)
                                    if returned_name!=result_record: raise ValueError(f"native record function '{fn.name}' cannot return {returned_name} as {result_record}")
                                    vals=[returned_fields[f][1] for f,_ in rd.fields]
                                else:
                                    raise ValueError(f"native record function '{fn.name}' must return a {result_record} constructor or compatible record call")
                                for (idx,(fname,ft)) in enumerate(rd.fields):
                                    lines_fn.append(f"  store {fn_llvm_type(ft.name)} {vals[idx]}, ptr %result_out_{fname}")
                                lines_fn.append("  ret void")
                            else:
                                typ,val=emit_fn_expr(inner.expr,branch_env,lines_fn)
                                if typ!=result: raise ValueError(f"native record function '{fn.name}' return type mismatch")
                                lines_fn.append(f"  ret {fn_llvm_type(result)} {val}")
                            branch_terminated=True; break
                        elif isinstance(inner,IfOp):
                            raise ValueError(f"native record function '{fn.name}' does not yet support nested if statements")
                        else:
                            raise ValueError(f"native record function '{fn.name}' supports let/return inside if")
                    if not branch_terminated:
                        raise ValueError(f"native record function '{fn.name}' if branch must return")
                terminated=True; break
            else:
                raise ValueError(f"native record function '{fn.name}' supports let/return/if")
        if not terminated: raise ValueError(f"native record function '{fn.name}' does not return on every native path")
        lines_fn.append("}"); fn_blocks.extend(lines_fn+[""])

    # Represent each record field as a native parallel array. This is an
    # implementation detail; S-Lang still exposes List<Record<T>>.
    lines=["; ModuleID = 'slang-record-collections'",'source_filename = "slang"','']
    if fn_blocks:
        lines.extend(fn_blocks)
    globals_data={}
    text_globals=[]
    for source,(rn,xs) in sources.items():
        specs=source_schema_fields.get(source, tuple((n,t.name) for n,t in records[rn].fields))
        for fname,typ_name in specs:
            vals=[x.args[findex[fname]] for x in xs]
            g=f"@rc_{source}_{fname}".replace('-','_')
            if typ_name == "Number":
                nums=[]
                for a in vals:
                    if not isinstance(a,Literal) or not isinstance(a.value,(int,float)) or isinstance(a.value,bool):
                        raise ValueError("native record collection requires literal numeric fields")
                    nums.append(float(a.value))
                elems=', '.join(f'double {v:.17e}' for v in nums) or 'double 0.0'
                lines.append(f'{g} = private constant [{len(nums) or 1} x double] [{elems}]')
            elif typ_name == "Boolean":
                if not all(isinstance(a,Literal) and isinstance(a.value,bool) for a in vals):
                    raise ValueError("native record collection requires literal Boolean fields")
                elems=', '.join('i1 1' if a.value else 'i1 0' for a in vals) or 'i1 0'
                lines.append(f'{g} = private constant [{len(vals) or 1} x i1] [{elems}]')
            elif typ_name == "Text":
                ptrs=[]
                for j,a in enumerate(vals):
                    if not isinstance(a,Literal) or not isinstance(a.value,str):
                        raise ValueError("native record collection requires literal Text fields")
                    key=f"rc_text_{source}_{fname}_{j}".replace('-','_')
                    encoded,length=_llvm_c_string(a.value)
                    lines.append(f'@{key} = private constant [{length} x i8] c"{encoded}"')
                    ptrs.append(f'ptr getelementptr inbounds ([{length} x i8], ptr @{key}, i64 0, i64 0)')
                elems=', '.join(ptrs) or 'ptr null'
                lines.append(f'{g} = private constant [{len(vals) or 1} x ptr] [{elems}]')
            globals_data[(source,fname)]=(g,len(vals),typ_name)
    lines += ['', 'declare i32 @printf(ptr, ...)', 'declare i32 @strcmp(ptr, ptr)', 'declare double @slang_reduce_f64(ptr, i64, double, i32)', '@rc_fmt = private constant [7 x i8] c"%.15g\\0A\\00"', '@rc_text_fmt = private constant [4 x i8] c"%s\\0A\\00"', '@rc_bool_fmt = private constant [4 x i8] c"%s\\0A\\00"', '@rc_true = private constant [5 x i8] c"true\\00"', '@rc_false = private constant [6 x i8] c"false\\00"', '', 'define i32 @main() {', 'entry:']
    desc={} ; current='entry'
    def field_expr(expr, ptrs, serial, expected=None):
        if isinstance(expr,(Field,Property)) and isinstance(expr.base,Name) and expr.base.name in {"row","item"}:
            fname=expr.name
            if fname not in ftypes: raise ValueError(f"unknown record field '{fname}'")
            typ=ftypes[fname]
            if expected and typ != expected: raise ValueError(f"record field '{fname}' must be {expected}")
            llvm_typ={'Number':'double','Boolean':'i1','Text':'ptr'}[typ]
            n=f"%rc_v_{serial}_{len(lines)}"
            lines.append(f"  {n} = load {llvm_typ}, ptr {ptrs[fname]}")
            return typ,n
        if isinstance(expr,Literal):
            if isinstance(expr.value,bool): return 'Boolean','1' if expr.value else '0'
            if isinstance(expr.value,(int,float)) and not isinstance(expr.value,bool): return 'Number',f"{float(expr.value):.17e}"
            if isinstance(expr.value,str):
                key=f"rc_expr_text_{serial}_{len(lines)}"; encoded,length=_llvm_c_string(expr.value)
                main_idx=lines.index('define i32 @main() {')
                lines.insert(main_idx, f'@{key} = private constant [{length} x i8] c"{encoded}"')
                return 'Text',f'getelementptr inbounds ([{length} x i8], ptr @{key}, i64 0, i64 0)'
        if isinstance(expr,Binary) and expr.op in {"+","-","*","/"}:
            at,av=field_expr(expr.left,ptrs,serial,'Number'); bt,bv=field_expr(expr.right,ptrs,serial,'Number')
            n=f"%rc_e_{serial}_{len(lines)}"; op={'+' :'fadd','-':'fsub','*':'fmul','/':'fdiv'}[expr.op]
            lines.append(f"  {n} = {op} double {av}, {bv}"); return 'Number',n
        raise ValueError("native record map supports field copies, literals, and numeric expressions")

    def numexpr(expr, ptrs, serial):
        typ,val=field_expr(expr,ptrs,serial,'Number')
        return val
        if isinstance(expr,Literal) and isinstance(expr.value,(int,float)) and not isinstance(expr.value,bool): return f"{float(expr.value):.17e}"
        if isinstance(expr,Binary) and expr.op in {"+","-","*","/"}:
            a=numexpr(expr.left,ptrs,serial); b=numexpr(expr.right,ptrs,serial)
            av=a.split(' = ',1)[0] if a.startswith('%') and ' = ' in a else a
            bv=b.split(' = ',1)[0] if b.startswith('%') and ' = ' in b else b
            if a.startswith('%') and ' = ' in a: lines.append('  '+a)
            if b.startswith('%') and ' = ' in b: lines.append('  '+b)
            n=f"%rc_e_{serial}_{len(lines)}"; lines.append(f"  {n} = {{{'+':'fadd','-':'fsub','*':'fmul','/':'fdiv'}[expr.op]}} double {av}, {bv}"); return n
        raise ValueError("record collection map supports numeric field expressions only")
    def pred(expr,ptrs,serial):
        if isinstance(expr,Logical):
            if expr.op=='not':
                a=pred(expr.left,ptrs,serial); n=f"%rc_not_{serial}_{len(lines)}"; lines.append(f"  {n} = xor i1 {a}, true"); return n
            if expr.op in {'and','or'}:
                a=pred(expr.left,ptrs,serial); b=pred(expr.right,ptrs,serial); n=f"%rc_l_{serial}_{len(lines)}"; lines.append(f"  {n} = {expr.op} i1 {a}, {b}"); return n
        if isinstance(expr,Call) and expr.name in fn_sigs:
            public_params,result,llvm_params,_result_record=fn_sigs[expr.name]
            if result != "Boolean": raise ValueError("where function must return Boolean")
            if len(public_params) != len(expr.args): raise ValueError("native record function call argument count mismatch")
            vals=[]
            for (kind,pname,fields),arg in zip(public_params,expr.args):
                if kind=="record":
                    if not (isinstance(arg,Name) and arg.name in {"row","item"}): raise ValueError("Record function arguments in native where must be row/item")
                    for fname,ft in fields:
                        ptr=ptrs.get(fname)
                        if ptr is None: raise ValueError(f"missing record field '{fname}'")
                        llvm_t=fn_llvm_type(ft); vv=f"%rc_fnarg_{serial}_{fname}_{len(lines)}"; lines.append(f"  {vv} = load {llvm_t}, ptr {ptr}"); vals.append(f"{llvm_t} {vv}")
                else:
                    typ,val=field_expr(arg,ptrs,serial,pname if False else fields)
                    vals.append(f"{fn_llvm_type(typ)} {val}")
            n=f"%rc_fn_{serial}_{len(lines)}"; lines.append(f"  {n} = call i1 @{expr.name}({', '.join(vals)})"); return n
        if not isinstance(expr,Compare): raise ValueError("record collection filter requires a comparison")
        at,av=field_expr(expr.left,ptrs,serial); bt,bv=field_expr(expr.right,ptrs,serial)
        if at != bt: raise ValueError("record collection filter comparison requires matching scalar types")
        n=f"%rc_p_{serial}_{len(lines)}"
        if at=='Number':
            pm={'>':'ogt','>=':'oge','<':'olt','<=':'ole','==':'oeq','!=':'one'}
            if expr.op not in pm: raise ValueError("unsupported Number comparison")
            lines.append(f"  {n} = fcmp {pm[expr.op]} double {av}, {bv}")
        elif at=='Boolean':
            if expr.op not in {'==','!='}: raise ValueError("Boolean record fields support == and !=")
            lines.append(f"  {n} = icmp {'eq' if expr.op=='==' else 'ne'} i1 {av}, {bv}")
        elif at=='Text':
            if expr.op not in {'==','!='}: raise ValueError("Text record fields support == and !=")
            cv=f"%rc_strcmp_{serial}_{len(lines)}"; lines.append(f"  {cv} = call i32 @strcmp(ptr {av}, ptr {bv})")
            lines.append(f"  {n} = icmp {'eq' if expr.op=='==' else 'ne'} i32 {cv}, 0")
        else: raise ValueError("unsupported record field type in filter")
        return n
    # descriptor: (field pointers, count, capacity, numeric/result kind)
    for serial,op in enumerate(ordered,1):
        if op.source in sources:
            src_rname,rxs=sources[op.source]; src_decl=records[src_rname]; cap=len(rxs)
            source_indices={f:globals_data[(op.source,f)][0] for f,t in src_decl.fields}; count=str(cap)
        else:
            source_indices,count,cap,kind,src_rname=desc[op.source]
            if kind!='record': raise ValueError("record collection pipeline cannot filter/map after numeric projection")
            src_decl=records[src_rname]
        # The current record type is part of the pipeline value, not a global
        # property of the original source. This allows Record<A> -> Record<B>
        # transformations while keeping subsequent row.field operations typed.
        decl=src_decl; rname=src_rname
        # 1.10.39: the current stage schema is authoritative for the
        # intermediate storage layout.  The AST declaration is used only to
        # materialize source constructor arguments and to validate function
        # signatures; row.field lowering uses this semantic schema.
        stage_schema = _schema_for_stage(op.source, output=True)
        if stage_schema is not None:
            ftypes = dict(stage_schema)
            schema_fields = tuple(stage_schema.items())
            ast_fields = tuple((n, t.name) for n, t in decl.fields)
            if ast_fields != schema_fields:
                raise ValueError(f"native backend schema contract for '{op.source}' does not match intermediate record storage layout")
        else:
            ftypes={n:t.name for n,t in decl.fields}
            schema_fields = tuple(ftypes.items())
        findex={n:i for i,(n,_) in enumerate(schema_fields)}
        # 1.8.74: every record-preserving stage must consume the actual
        # preceding record buffer. Previously Record->Record map and scalar
        # projection after a filter used the original source arrays with the
        # filtered count, which was only accidentally correct when discarded
        # rows happened to be at the end.
        source_indices = source_indices
        if isinstance(op,FilterOp):
            new={}; bufs={}
            for f,typ_name in schema_fields:
                llvm_typ={'Number':'double','Boolean':'i1','Text':'ptr'}[typ_name]
                buf=f"%rcb_{serial}_{f}"; lines.append(f"  {buf} = alloca [{cap or 1} x {llvm_typ}]"); bufs[f]=buf
            cnt=f"%rcc_{serial}"; lines += [f"  {cnt} = alloca i64",f"  store i64 0, ptr {cnt}"]
            loop=f"rcl_{serial}"; body=f"rcbody_{serial}"; keep=f"rckeep_{serial}"; skip=f"rcskip_{serial}"; done=f"rcdone_{serial}"
            lines += [f"  br label %{loop}",f"{loop}:",f"  %ri_{serial} = phi i64 [ 0, %{current} ], [ %rn_{serial}, %{skip} ]",f"  %rnmax_{serial} = add i64 0, {count}" if str(count).isdigit() else f"  %rnmax_{serial} = load i64, ptr {count}",f"  %ric_{serial} = icmp ult i64 %ri_{serial}, %rnmax_{serial}",f"  br i1 %ric_{serial}, label %{body}, label %{done}",f"{body}:"]
            ptrs={}
            for f in bufs:
                pv=f"%rc_ptr_{serial}_{f}"; llvm_typ={'Number':'double','Boolean':'i1','Text':'ptr'}[ftypes[f]]
                lines.append(f"  {pv} = getelementptr inbounds [{cap} x {llvm_typ}], ptr {source_indices[f]}, i64 0, i64 %ri_{serial}")
                ptrs[f]=pv
            keepv=pred(op.predicate.expr,ptrs,serial)
            lines += [f"  br i1 {keepv}, label %{keep}, label %{skip}",f"{keep}:",f"  %rcoc_{serial} = load i64, ptr {cnt}"]
            for f,buf in bufs.items():
                llvm_typ={'Number':'double','Boolean':'i1','Text':'ptr'}[ftypes[f]]
                lines += [f"  %rcdp_{serial}_{f} = getelementptr [{cap or 1} x {llvm_typ}], ptr {buf}, i64 0, i64 %rcoc_{serial}",f"  %rcsv_{serial}_{f} = load {llvm_typ}, ptr {ptrs[f]}",f"  store {llvm_typ} %rcsv_{serial}_{f}, ptr %rcdp_{serial}_{f}"]
            lines += [f"  %rcon_{serial} = add i64 %rcoc_{serial}, 1",f"  store i64 %rcon_{serial}, ptr {cnt}",f"  br label %{skip}",f"{skip}:",f"  %rn_{serial} = add i64 %ri_{serial}, 1",f"  br label %{loop}",f"{done}:"]
            desc[op.result]=({f:buf for f,buf in bufs.items()},cnt,cap,'record',rname); current=done
        else:
            # 1.10.29: typed user functions may transform one declared Record
            # type into another declared Record type. The function ABI uses the
            # source record fields as input scalars and a separately typed output
            # buffer, so the new record schema becomes the pipeline schema for
            # subsequent stages.
            if isinstance(op.expr, Call) and op.expr.name in fn_sigs and fn_sigs[op.expr.name][1] == "Record":
                public_params,result,llvm_params,result_record = fn_sigs[op.expr.name]
                if result_record not in records:
                    raise ValueError("native record map function return type is not a declared Record")
                out_decl = records[result_record]
                if len(public_params) != len(op.expr.args):
                    raise ValueError("native record map function argument count mismatch")
                target_schema = _schema_for_stage(op.result, output=True)
                if target_schema is None:
                    target_schema = {n: t.name for n, t in out_decl.fields}
                expected_target = tuple((n, t.name) for n, t in out_decl.fields)
                if tuple(target_schema.items()) != expected_target:
                    raise ValueError(f"native backend schema contract for '{op.result}' does not match function result record layout")
                bufs={}
                for f,typ_name in target_schema.items():
                    llvm_typ={'Number':'double','Boolean':'i1','Text':'ptr'}[typ_name]
                    bufs[f]=f"%rcfbuf_{serial}_{f}"; lines.append(f"  {bufs[f]} = alloca [{cap or 1} x {llvm_typ}]")
                loop=f"rcfl_{serial}"; body=f"rcfbody_{serial}"; done=f"rcfdone_{serial}"
                lines += [f"  br label %{loop}",f"{loop}:",f"  %fi_{serial} = phi i64 [ 0, %{current} ], [ %fn_{serial}, %{body} ]",f"  %fmax_{serial} = add i64 0, {count}" if str(count).isdigit() else f"  %fmax_{serial} = load i64, ptr {count}",f"  %fc_{serial} = icmp ult i64 %fi_{serial}, %fmax_{serial}",f"  br i1 %fc_{serial}, label %{body}, label %{done}",f"{body}:"]
                ptrs={}
                for f,t in decl.fields:
                    llvm_typ={'Number':'double','Boolean':'i1','Text':'ptr'}[t.name]
                    ptr=f"%rc_fptr_{serial}_{f}"; lines.append(f"  {ptr} = getelementptr inbounds [{cap} x {llvm_typ}], ptr {source_indices[f]}, i64 0, i64 %fi_{serial}"); ptrs[f]=ptr
                args=[]
                for (kind,pname,fields),arg in zip(public_params,op.expr.args):
                    if kind == "record":
                        if not (isinstance(arg,Name) and arg.name in {"row","item"}): raise ValueError("Record map function arguments must be row/item")
                        for fname,ft in fields:
                            llvm_t=fn_llvm_type(ft); vv=f"%rc_farg_{serial}_{fname}_{len(lines)}"; lines.append(f"  {vv} = load {llvm_t}, ptr {ptrs[fname]}"); args.append(f"{llvm_t} {vv}")
                    else:
                        typ,val=field_expr(arg,ptrs,serial,fields); args.append(f"{fn_llvm_type(typ)} {val}")
                out_args=[]
                for fname,ft in out_decl.fields:
                    llvm_t=fn_llvm_type(ft.name); dp=f"%rc_fdst_{serial}_{fname}"; lines.append(f"  {dp} = getelementptr [{cap or 1} x {llvm_t}], ptr {bufs[fname]}, i64 0, i64 %fi_{serial}"); out_args.append(f"ptr {dp}")
                lines.append(f"  call void @{op.expr.name}({', '.join(out_args + args)})")
                lines += [f"  %fn_{serial} = add i64 %fi_{serial}, 1",f"  br label %{loop}",f"{done}:"]
                desc[op.result]=(bufs,count,cap,'record',result_record); current=done; continue
            # 1.10.31: typed scalar-returning functions may also consume the
            # current record row. This keeps function composition symmetric with
            # Record-returning maps while preserving the existing scalar collection ABI.
            if isinstance(op.expr, Call) and op.expr.name in fn_sigs and fn_sigs[op.expr.name][1] in {"Number", "Boolean"}:
                public_params,result,llvm_params,result_record = fn_sigs[op.expr.name]
                if len(public_params) != len(op.expr.args):
                    raise ValueError("native scalar record-map function argument count mismatch")
                llvm_out = fn_llvm_type(result)
                out=f"%rcfscalar_{serial}"; lines.append(f"  {out} = alloca [{cap or 1} x {llvm_out}]")
                loop=f"rcsl_{serial}"; body=f"rcsbody_{serial}"; done=f"rcsdone_{serial}"
                lines += [f"  br label %{loop}", f"{loop}:", f"  %si_{serial} = phi i64 [ 0, %{current} ], [ %sn_{serial}, %{body} ]", f"  %smax_{serial} = add i64 0, {count}" if str(count).isdigit() else f"  %smax_{serial} = load i64, ptr {count}", f"  %sc_{serial} = icmp ult i64 %si_{serial}, %smax_{serial}", f"  br i1 %sc_{serial}, label %{body}, label %{done}", f"{body}:"]
                ptrs={}
                for f,t in decl.fields:
                    llvm_typ={'Number':'double','Boolean':'i1','Text':'ptr'}[t.name]
                    ptr=f"%rc_sptr_{serial}_{f}"; lines.append(f"  {ptr} = getelementptr inbounds [{cap} x {llvm_typ}], ptr {source_indices[f]}, i64 0, i64 %si_{serial}"); ptrs[f]=ptr
                call_args=[]
                for (kind,pname,fields),arg in zip(public_params,op.expr.args):
                    if kind == "record":
                        for fname,ft in fields:
                            llvm_t=fn_llvm_type(ft); vv=f"%rc_sarg_{serial}_{fname}_{len(lines)}"; lines.append(f"  {vv} = load {llvm_t}, ptr {ptrs[fname]}"); call_args.append(f"{llvm_t} {vv}")
                    else:
                        typ,val=field_expr(arg,ptrs,serial,fields); call_args.append(f"{fn_llvm_type(typ)} {val}")
                rv=f"%rc_sval_{serial}"; lines.append(f"  {rv} = call {llvm_out} @{op.expr.name}({', '.join(call_args)})")
                dst=f"%rc_sdst_{serial}"; lines.append(f"  {dst} = getelementptr [{cap or 1} x {llvm_out}], ptr {out}, i64 0, i64 %si_{serial}"); lines.append(f"  store {llvm_out} {rv}, ptr {dst}")
                lines += [f"  %sn_{serial} = add i64 %si_{serial}, 1", f"  br label %{loop}", f"{done}:"]
                desc[op.result]=(out,count,cap,result,result); current=done; continue

            # A map may either project a Number field or construct another value
            # of the same named Record type. Record construction keeps the
            # collection at List<Record<T>> instead of forcing an early scalar projection.
            if isinstance(op.expr, Call) and op.expr.name in records:
                target_rname=op.expr.name
                target_decl=records[target_rname]
                target_schema = _schema_for_stage(op.result, output=True)
                if target_schema is None:
                    target_schema = {n: t.name for n, t in target_decl.fields}
                expected_target = tuple((n, t.name) for n, t in target_decl.fields)
                if tuple(target_schema.items()) != expected_target:
                    raise ValueError(f"native backend schema contract for '{op.result}' does not match constructor result layout")
                if any(t not in {"Number","Boolean","Text"} for t in target_schema.values()):
                    raise ValueError("native record map target fields must be Number, Boolean, or Text")
                if len(op.expr.args) != len(target_schema): raise ValueError("record constructor arity mismatch in native map")
                bufs={}
                for f,typ_name in target_schema.items():
                    llvm_typ={'Number':'double','Boolean':'i1','Text':'ptr'}[typ_name]
                    bufs[f]=f"%rcmbuf_{serial}_{f}"; lines.append(f"  {bufs[f]} = alloca [{cap or 1} x {llvm_typ}]")
                loop=f"rcml_{serial}"; body=f"rcmbody_{serial}"; done=f"rcmdone_{serial}"
                lines += [f"  br label %{loop}",f"{loop}:",f"  %mi_{serial} = phi i64 [ 0, %{current} ], [ %mn_{serial}, %{body} ]",f"  %mmax_{serial} = add i64 0, {count}" if str(count).isdigit() else f"  %mmax_{serial} = load i64, ptr {count}",f"  %mc_{serial} = icmp ult i64 %mi_{serial}, %mmax_{serial}",f"  br i1 %mc_{serial}, label %{body}, label %{done}",f"{body}:"]
                ptrs={}
                for f,t in decl.fields:
                    llvm_typ={'Number':'double','Boolean':'i1','Text':'ptr'}[t.name]
                    ptr=f"%rc_srcptr_{serial}_{f}"; lines.append(f"  {ptr} = getelementptr inbounds [{cap} x {llvm_typ}], ptr {source_indices[f]}, i64 0, i64 %mi_{serial}"); ptrs[f]=ptr
                for (fname,typ_name),arg in zip(target_schema.items(),op.expr.args):
                    typ,val=field_expr(arg,ptrs,serial,typ_name)
                    llvm_typ={'Number':'double','Boolean':'i1','Text':'ptr'}[typ]
                    dst=f"%rc_dst_{serial}_{fname}"; lines.append(f"  {dst} = getelementptr [{cap or 1} x {llvm_typ}], ptr {bufs[fname]}, i64 0, i64 %mi_{serial}"); lines.append(f"  store {llvm_typ} {val}, ptr {dst}")
                lines += [f"  %mn_{serial} = add i64 %mi_{serial}, 1",f"  br label %{loop}",f"{done}:"]
                desc[op.result]=(bufs,count,cap,'record',target_rname); current=done; continue
            if not isinstance(op.expr,(Field,Property)) or op.expr.name not in ftypes or ftypes[op.expr.name] not in {'Number','Boolean','Text'}: raise ValueError("native record collection map currently projects a scalar field or constructs the same Record type")
            f=op.expr.name; projected_type=ftypes[f]; llvm_proj={'Number':'double','Boolean':'i1','Text':'ptr'}[projected_type]; out=f"%rcmb_{serial}"; lines.append(f"  {out} = alloca [{cap or 1} x {llvm_proj}]")
            loop=f"rcml_{serial}"; body=f"rcmbody_{serial}"; done=f"rcmdone_{serial}"
            lines += [f"  br label %{loop}",f"{loop}:",f"  %mi_{serial} = phi i64 [ 0, %{current} ], [ %mn_{serial}, %{body} ]",f"  %mmax_{serial} = add i64 0, {count}" if str(count).isdigit() else f"  %mmax_{serial} = load i64, ptr {count}",f"  %mc_{serial} = icmp ult i64 %mi_{serial}, %mmax_{serial}",f"  br i1 %mc_{serial}, label %{body}, label %{done}",f"{body}:"]
            srcptr=source_indices[f] if isinstance(source_indices,dict) else source_indices[f]
            ptr=f"%rc_mptr_{serial}"
            lines += [f"  {ptr} = getelementptr inbounds [{cap} x {llvm_proj}], ptr {srcptr}, i64 0, i64 %mi_{serial}", f"  %mv_{serial} = load {llvm_proj}, ptr {ptr}",f"  %md_{serial} = getelementptr [{cap or 1} x {llvm_proj}], ptr {out}, i64 0, i64 %mi_{serial}",f"  store {llvm_proj} %mv_{serial}, ptr %md_{serial}",f"  %mn_{serial} = add i64 %mi_{serial}, 1",f"  br label %{loop}",f"{done}:"]
            desc[op.result]=(out,count,cap,projected_type); current=done
    show={x.name for x in p.show_exprs if isinstance(x,Name)}
    for j,(name,d) in enumerate(desc.items()):
        if name not in show: continue
        if len(d) == 5 and d[3] == 'scalar':
            ptr,cnt,cap,_,kind=d
        else:
            ptr,cnt,cap,kind=d[:4]
        if kind not in {'number','Number','Boolean','Text'}: raise ValueError("map a record field before show")
        kind = 'Number' if kind == 'number' else kind
        llvm_show={'Number':'double','Boolean':'i1','Text':'ptr'}[kind]
        loop=f"rcshow{j}"; body=f"rcshowb{j}"; done=f"rcshowd{j}"
        lines += [f"  br label %{loop}",f"{loop}:",f"  %si_{j} = phi i64 [ 0, %{current} ], [ %sn_{j}, %{body} ]",f"  %sc_{j} = add i64 0, {cnt}" if str(cnt).isdigit() else f"  %sc_{j} = load i64, ptr {cnt}",f"  %sx_{j} = icmp ult i64 %si_{j}, %sc_{j}",f"  br i1 %sx_{j}, label %{body}, label %{done}",f"{body}:",f"  %sp_{j} = getelementptr {llvm_show}, ptr {ptr}, i64 %si_{j}",f"  %sv_{j} = load {llvm_show}, ptr %sp_{j}"]
        if kind=='Number':
            lines.append(f"  call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([7 x i8], ptr @rc_fmt, i64 0, i64 0), double %sv_{j})")
        elif kind=='Text':
            lines.append(f"  call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([4 x i8], ptr @rc_text_fmt, i64 0, i64 0), ptr %sv_{j})")
        else:
            bp=f"%rc_boolptr_{j}"; lines += [f"  {bp} = select i1 %sv_{j}, ptr getelementptr inbounds ([5 x i8], ptr @rc_true, i64 0, i64 0), ptr getelementptr inbounds ([6 x i8], ptr @rc_false, i64 0, i64 0)",f"  call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([4 x i8], ptr @rc_bool_fmt, i64 0, i64 0), ptr {bp})"]
        lines += [f"  %sn_{j} = add i64 %si_{j}, 1",f"  br label %{loop}",f"{done}:"]
    lines += ['  ret i32 0','}','']
    return '\n'.join(lines)

def record_llvm_ir(p: Program):
    """Lower a small immutable named-record subset to native LLVM structs.

    Records are represented as private LLVM structs with scalar fields.  The
    first native record milestone deliberately supports only Number, Boolean,
    and Text fields plus constructor bindings and field projection.  This keeps
    the representation deterministic while leaving collection-of-records and
    mutable records for later stages.
    """
    validate(p)
    if not p.ast.records:
        raise ValueError("native record backend requires at least one record declaration")
    if p.ast.functions or p.ast.filters or p.ast.maps or p.ast.sorts or p.ast.aggregates or p.ast.reduces:
        raise ValueError("native record backend currently accepts scalar record bindings and field projections")
    if p.bodies or p.simulation or p.ast.sequences or p.ast.goals or p.ast.path_goals or p.ast.satisfy_goals:
        raise ValueError("native record backend accepts scalar record bindings only")

    records = {r.name: r for r in p.ast.records}
    fields = {}
    for rname, decl in records.items():
        resolved = {}
        for fname, ref in decl.fields:
            if ref.name not in {"Number", "Boolean", "Text", *records.keys()}:
                raise ValueError(f"native record backend does not support field type '{ref.name}' in '{rname}.{fname}'")
            resolved[fname] = ref.name if ref.name in {"Number", "Boolean", "Text"} else f"Record:{ref.name}"
        fields[rname] = resolved

    def llvm_type(name):
        if name in {"Number", "Boolean", "Text"}:
            return {"Number":"double", "Boolean":"i1", "Text":"ptr"}[name]
        if name.startswith("Record:") and name.split(":",1)[1] in records:
            # Nested records are represented by stable pointers to their
            # private LLVM structs; the pointer is the S-Lang value.
            return "ptr"
        raise ValueError(f"unknown native record type '{name}'")

    def struct_name(rname):
        return f"%record.{rname}"

    # LLVM type declarations are emitted once per record.  Values live in
    # entry-block allocas, so bindings can refer to earlier records naturally.
    lines=["; ModuleID = 'slang-records'", 'source_filename = "slang"', '']
    for rname, decl in records.items():
        parts=', '.join(llvm_type(fields[rname][fname]) for fname, _ in decl.fields)
        lines.append(f"{struct_name(rname)} = type {{ {parts} }}")
    lines += ['']

    globals_out=[]
    env={}
    declarations=[]
    counter=[0]

    def fresh(prefix):
        n=counter[0]; counter[0]+=1; return f"%{prefix}_{n}"

    def field_index(rname, fname):
        for i,(name,_) in enumerate(records[rname].fields):
            if name == fname:
                return i
        raise ValueError(f"unknown field '{fname}' on record '{rname}'")

    def emit(expr):
        if isinstance(expr, Literal):
            if isinstance(expr.value, bool): return ("Boolean", "1" if expr.value else "0", False)
            if isinstance(expr.value, (int,float)) and not isinstance(expr.value,bool): return ("Number", f"{float(expr.value):.17e}", False)
            if isinstance(expr.value, str):
                key=f"record_str_{len(globals_out)}"; encoded,length=_llvm_c_string(expr.value)
                globals_out.append((key,encoded,length))
                return ("Text", f"getelementptr inbounds ([{length} x i8], ptr @{key}, i64 0, i64 0)", False)
            raise ValueError("native record backend supports only scalar literals")
        if isinstance(expr, Name):
            if expr.name not in env: raise ValueError(f"native record backend cannot resolve '{expr.name}'")
            return env[expr.name]
        if isinstance(expr, Call) and expr.name in records:
            decl=records[expr.name]
            if len(expr.args) != len(decl.fields):
                raise ValueError(f"record '{expr.name}' expects {len(decl.fields)} field value(s)")
            ptr=fresh("record")
            lines.append(f"  {ptr} = alloca {struct_name(expr.name)}")
            for idx,(fname,_) in enumerate(decl.fields):
                typ,val,_owned=emit(expr.args[idx])
                expected=fields[expr.name][fname]
                if typ != expected: raise ValueError(f"record '{expr.name}.{fname}' expects {expected}, got {typ}")
                fp=fresh("record_field")
                lines.append(f"  {fp} = getelementptr inbounds {struct_name(expr.name)}, ptr {ptr}, i32 0, i32 {idx}")
                lines.append(f"  store {llvm_type(typ)} {val}, ptr {fp}")
            return (f"Record:{expr.name}", ptr, False)
        if isinstance(expr, Property):
            # The base may itself be a nested property, e.g. order.customer.name.
            base_typ, base_ptr, _ = emit(expr.base)
            if not base_typ.startswith("Record:"):
                raise ValueError("native record field access requires a native record value")
            rname=base_typ.split(":",1)[1]
            if expr.name not in fields[rname]: raise ValueError(f"unknown field '{expr.name}' on record '{rname}'")
            idx=field_index(rname,expr.name); typ=fields[rname][expr.name]
            fp=fresh("load_field")
            lines.append(f"  {fp} = getelementptr inbounds {struct_name(rname)}, ptr {base_ptr}, i32 0, i32 {idx}")
            value=fresh("field_value")
            lines.append(f"  {value} = load {llvm_type(typ)}, ptr {fp}")
            return (typ,value,typ=="Text")
        if isinstance(expr, Binary) and expr.op in {"+","-","*","/"}:
            lt,lv,_=emit(expr.left); rt,rv,_=emit(expr.right)
            if lt!="Number" or rt!="Number": raise ValueError("native record arithmetic requires Number fields")
            op={"+":"fadd","-":"fsub","*":"fmul","/":"fdiv","%":"frem"}[expr.op]; tmp=fresh("record_expr")
            lines.append(f"  {tmp} = {op} double {lv}, {rv}"); return ("Number",tmp,False)
        if isinstance(expr, Compare):
            lt,lv,_=emit(expr.left); rt,rv,_=emit(expr.right)
            if lt!=rt or lt not in {"Number","Boolean"}: raise ValueError("native record comparison requires matching Number or Boolean values")
            if lt=="Number": pred={">":"ogt",">=":"oge","<":"olt","<=":"ole","==":"oeq","!=":"one"}.get(expr.op)
            else: pred={"==":"eq","!=":"ne"}.get(expr.op)
            if pred is None: raise ValueError(f"unsupported comparison '{expr.op}'")
            tmp=fresh("record_cmp"); lines.append(f"  {tmp} = {'fcmp '+pred+' double '+lv+', '+rv if lt=='Number' else 'icmp '+pred+' i1 '+lv+', '+rv}")
            return ("Boolean",tmp,False)
        raise ValueError(f"native record backend does not support expression {type(expr).__name__}")

    # Bindings are emitted in source order.  A record constructor is immutable
    # from the S-Lang user's perspective; the backing alloca is never exposed.
    for binding in p.ast.bindings:
        value=emit(binding.expr)
        env[binding.name]=value

    show_values=[]
    for expr in p.show_exprs:
        show_values.append(emit(expr))

    # Capture constructor/property instructions generated above before adding
    # the module-level declarations and main function.
    body_instr=[line for line in lines if line.startswith("  ")]
    module_lines=[line for line in lines if not line.startswith("  ")]
    for name,encoded,length in globals_out:
        module_lines.insert(2, f"@{name} = private constant [{length} x i8] c\"{encoded}\"")
    module_lines += ["", "declare i32 @printf(ptr, ...)", "", "define i32 @main() {", "entry:"]
    lines=module_lines + body_instr
    for index,(typ,val,owned) in enumerate(show_values):
        if typ=='Number':
            fmt=f"@record_fmt_num_{index}"; lines.insert(2, f'{fmt} = private constant [7 x i8] c"%.15g\\0A\\00"')
            lines.append(f'  call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([7 x i8], ptr {fmt}, i64 0, i64 0), double {val})')
        elif typ=='Boolean':
            fmt=f"@record_fmt_bool_{index}"; tr=f"@record_true_{index}"; fa=f"@record_false_{index}"
            lines.insert(2, f'{fmt} = private constant [4 x i8] c"%s\\0A\\00"'); lines.insert(2, f'{tr} = private constant [5 x i8] c"true\\00"'); lines.insert(2, f'{fa} = private constant [6 x i8] c"false\\00"')
            bp=f"%record_bool_ptr_{index}"; lines.append(f'  {bp} = select i1 {val}, ptr getelementptr inbounds ([5 x i8], ptr {tr}, i64 0, i64 0), ptr getelementptr inbounds ([6 x i8], ptr {fa}, i64 0, i64 0)'); lines.append(f'  call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([4 x i8], ptr {fmt}, i64 0, i64 0), ptr {bp})')
        elif typ=='Text':
            fmt=f"@record_fmt_text_{index}"; lines.insert(2, f'{fmt} = private constant [4 x i8] c"%s\\0A\\00"'); lines.append(f'  call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([4 x i8], ptr {fmt}, i64 0, i64 0), ptr {val})')
        elif typ.startswith('Record:'):
            raise ValueError("cannot show a whole Record yet; show one of its fields")
        else:
            raise ValueError(f"cannot show native record value of type {typ}")
    lines += ['  ret i32 0', '}', '']
    return '\n'.join(lines)


def system_llvm_ir(p: Program):
    """Emit a native executable for scalar filesystem/system operations."""
    validate(p)
    supported_calls = {"exists", "file_size", "is_file", "is_directory", "write", "read", "read_lines", "list_directory", "list_files", "list_directories", "make_directory", "make_directories", "remove_directory", "remove_directory_tree", "remove_file", "copy_file", "move_file", "write_lines", "basename", "dirname", "extension", "join_path", "normalize_path", "arguments", "environment", "run_process", "run_program", "run_program_with_environment", "current_directory", "platform_name", "process_id", "sleep_seconds", "home_directory", "temp_directory", "executable_path", "command_exists", "trim", "lower", "upper", "starts_with", "ends_with", "replace", "split"}
    if p.bodies or p.simulation or p.ast.filters or p.ast.maps or p.ast.sorts or p.ast.aggregates or p.ast.reduces or p.ast.sequences or p.ast.goals or p.ast.path_goals or p.ast.satisfy_goals:
        raise ValueError("native system backend accepts scalar bindings and show expressions only")
    for binding in p.ast.bindings:
        def calls(expr):
            if isinstance(expr, Call): return {expr.name} | set().union(*(calls(a) for a in expr.args))
            if isinstance(expr, (Binary, Compare, Logical)): return calls(expr.left) | (calls(expr.right) if getattr(expr, "right", None) is not None else set())
            return set()
        unknown = calls(binding.expr) - supported_calls
        if unknown:
            raise ValueError("native system backend does not support call(s): " + ", ".join(sorted(unknown)))
    env={}; globals_out=[]; body=[]; declarations=[]
    for binding in p.ast.bindings:
        typ, value = _native_system_call_expr(binding.expr, env, globals_out, declarations)
        env[binding.name]=(typ, value)
    # Repeated declaration strings are removed while preserving order.
    show_values=[_native_system_call_expr(expr, env, globals_out, declarations) for expr in p.show_exprs]
    seen=set(); declarations=[x for x in declarations if not (x in seen or seen.add(x))]
    lines=["; ModuleID = 'slang-system'", 'source_filename = "slang"', '']
    for name, encoded, length in globals_out:
        lines.append(f"@{name} = private constant [{length} x i8] c\"{encoded}\"")
    lines += ['', *[d for d in declarations if d.startswith('declare ')], 'declare i32 @printf(ptr, ...)', 'declare i64 @slang_text_list_count(ptr)', 'declare ptr @slang_text_list_item(ptr, i64)', 'declare ptr @slang_text_list_new(i64)', 'declare i1 @slang_text_list_set(ptr, i64, ptr)', 'declare void @slang_text_free(ptr)', 'declare void @slang_text_list_free(ptr)', '']
    lines += ['define i32 @main(i32 %argc, ptr %argv) {', 'entry:']
    # declarations generated while evaluating expressions contain both LLVM
    # declarations and instructions; only instructions belong in main.
    for d in declarations:
        if not d.startswith('declare '): lines.append(d)
    for index, (typ, value) in enumerate(show_values):
        if typ == 'double':
            fmt_name=f"fmt_num_{index}"; text=f"%.15g\\0A\\00"; n=7
            lines.insert(2, f"@{fmt_name} = private constant [{n} x i8] c\"{text}\"")
            lines.append(f"  %show_{index} = call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([{n} x i8], ptr @{fmt_name}, i64 0, i64 0), double {value})")
        elif typ == 'i1':
            fmt_name=f"fmt_bool_{index}"; text="%s\\0A\\00"; n=4
            true_name=f"bool_true_{index}"; false_name=f"bool_false_{index}"
            lines.insert(2, f"@{fmt_name} = private constant [{n} x i8] c\"%s\\0A\\00\"")
            lines.insert(2, f"@{true_name} = private constant [5 x i8] c\"true\\00\"")
            lines.insert(2, f"@{false_name} = private constant [6 x i8] c\"false\\00\"")
            ptr=f"%show_bool_ptr_{index}"
            lines.append(f"  {ptr} = select i1 {value}, ptr getelementptr inbounds ([5 x i8], ptr @{true_name}, i64 0, i64 0), ptr getelementptr inbounds ([6 x i8], ptr @{false_name}, i64 0, i64 0)")
            lines.append(f"  %show_{index} = call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([{n} x i8], ptr @{fmt_name}, i64 0, i64 0), ptr {ptr})")
        elif typ == 'text':
            fmt_name=f"fmt_text_{index}"; n=4
            lines.insert(2, f"@{fmt_name} = private constant [{n} x i8] c\"%s\\0A\\00\"")
            lines.append(f"  %show_{index} = call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([{n} x i8], ptr @{fmt_name}, i64 0, i64 0), ptr {value})")
        elif typ == 'text_list':
            count=f"%show_list_count_{index}"
            loop=f"list_loop_{index}"; body=f"list_body_{index}"; done=f"list_done_{index}"
            lines.insert(2, f"@fmt_text_list_{index} = private constant [4 x i8] c\"%s\\0A\\00\"")
            lines.append(f"  {count} = call i64 @slang_text_list_count(ptr {value})")
            lines.append(f"  br label %{loop}")
            lines.append(f"{loop}:")
            lines.append(f"  %list_i_{index} = phi i64 [ 0, %entry ], [ %list_next_{index}, %{body} ]")
            lines.append(f"  %list_cond_{index} = icmp ult i64 %list_i_{index}, {count}")
            lines.append(f"  br i1 %list_cond_{index}, label %{body}, label %{done}")
            lines.append(f"{body}:")
            lines.append(f"  %list_item_{index} = call ptr @slang_text_list_item(ptr {value}, i64 %list_i_{index})")
            lines.append(f"  %list_print_{index} = call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([4 x i8], ptr @fmt_text_list_{index}, i64 0, i64 0), ptr %list_item_{index})")
            lines.append(f"  %list_next_{index} = add i64 %list_i_{index}, 1")
            lines.append(f"  br label %{loop}")
            lines.append(f"{done}:")
        else:
            raise ValueError(f"cannot show native value of type {typ}")
    lines += ['  ret i32 0', '}', '']
    return '\n'.join(lines)


def _native_declared_scalar_type(ref):
    """Map an explicit S-Lang scalar declaration to its LLVM ABI type."""
    if ref is None:
        raise ValueError("native function backend requires explicit parameter and return types")
    name = ref.name
    if name == "Number":
        return "double"
    if name == "Boolean":
        return "i1"
    raise ValueError(f"native function backend currently supports only Number and Boolean, got {name}")


def _native_declared_abi_type(ref, *, allow_list=False):
    """Map supported S-Lang declarations to stable LLVM ABI types.

    List<Number> is represented as an opaque pointer to the C runtime's
    SlangNumberList. The pointer is intentionally opaque in LLVM IR: all
    element access must go through the checked runtime ABI.
    """
    if ref is not None and ref.name == "List":
        if not allow_list or len(ref.args) != 1 or ref.args[0].name != "Number" or ref.args[0].args:
            raise ValueError("native function backend supports List<Number> parameters only")
        return "ptr"
    return _native_declared_scalar_type(ref)


def _native_function_llvm_ir(p: Program):
    """Lower explicitly typed user functions with deterministic scalar control flow."""
    if not p.ast.functions:
        return None
    signatures = {}
    for fn in p.ast.functions:
        if fn.type_params:
            raise ValueError(f"native function backend does not yet lower generic function '{fn.name}'")
        params = tuple(_native_declared_abi_type(ref, allow_list=True) for _, ref in fn.parameters)
        result = _native_declared_abi_type(fn.return_type, allow_list=False)
        signatures[fn.name] = (params, result)

    globals_out=[]; declarations=[
        "declare i64 @slang_number_list_count(ptr)",
        "declare double @slang_number_list_item(ptr, i64)",
        "declare ptr @slang_number_list_new(i64)",
        "declare i32 @slang_number_list_set(ptr, i64, double)",
        "declare i32 @slang_number_list_append(ptr, double)",
        "declare void @slang_number_list_free(ptr)",
    ]; function_blocks=[]
    counter=[0]

    def fresh(prefix):
        value=f"{prefix}_{counter[0]}"; counter[0]+=1; return value

    def emit_expr(expr, env, lines):
        if isinstance(expr, Literal):
            if isinstance(expr.value, bool): return "i1", "1" if expr.value else "0"
            if isinstance(expr.value, (int,float)) and not isinstance(expr.value,bool): return "double", f"{float(expr.value):.17e}"
            raise ValueError("native function backend supports only Number and Boolean literals")
        if isinstance(expr, Name):
            if expr.name not in env: raise ValueError(f"native function backend cannot resolve '{expr.name}'")
            return env[expr.name]
        if isinstance(expr, Binary) and expr.op in {"+","-","*","/"}:
            lt,lv=emit_expr(expr.left,env,lines); rt,rv=emit_expr(expr.right,env,lines)
            if lt != "double" or rt != "double": raise ValueError("native function arithmetic requires Number operands")
            op={"+":"fadd","-":"fsub","*":"fmul","/":"fdiv","%":"frem"}[expr.op]
            tmp=f"%{fresh('expr')}"; lines.append(f"  {tmp} = {op} double {lv}, {rv}"); return "double",tmp
        if isinstance(expr, Compare) and expr.op in {">",">=","<","<=","==","!="}:
            lt,lv=emit_expr(expr.left,env,lines); rt,rv=emit_expr(expr.right,env,lines)
            if lt != rt or lt not in {"double","i1"}: raise ValueError("native comparison requires matching scalar operands")
            if lt == "double": pred={">":"ogt",">=":"oge","<":"olt","<=":"ole","==":"oeq","!=":"one"}[expr.op]; ins=f"fcmp {pred} double {lv}, {rv}"
            else: pred={"==":"eq","!=":"ne"}.get(expr.op)
            if lt == "i1":
                if pred is None: raise ValueError("ordered comparison is invalid for Boolean")
                ins=f"icmp {pred} i1 {lv}, {rv}"
            tmp=f"%{fresh('cmp')}"; lines.append(f"  {tmp} = {ins}"); return "i1",tmp
        if isinstance(expr, Logical):
            if expr.op == "not":
                typ,val=emit_expr(expr.left,env,lines)
                if typ != "i1": raise ValueError("native logical operators require Boolean operands")
                tmp=f"%{fresh('not')}"; lines.append(f"  {tmp} = xor i1 {val}, true"); return "i1",tmp
            lt,lv=emit_expr(expr.left,env,lines); rt,rv=emit_expr(expr.right,env,lines)
            if lt != "i1" or rt != "i1": raise ValueError("native logical operators require Boolean operands")
            tmp=f"%{fresh('logic')}"; lines.append(f"  {tmp} = {'and' if expr.op=='and' else 'or'} i1 {lv}, {rv}"); return "i1",tmp
        if isinstance(expr, Conditional):
            ctyp, cval = emit_expr(expr.condition, env, lines)
            if ctyp != "i1":
                raise ValueError("native conditional expression condition must be Boolean")
            ttyp, tval = emit_expr(expr.then_expr, env, lines)
            etyp, eval_ = emit_expr(expr.else_expr, env, lines)
            if ttyp != etyp or ttyp not in {"double", "i1"}:
                raise ValueError("native conditional expression requires matching Number or Boolean branches")
            tmp=f"%{fresh('select')}"
            lines.append(f"  {tmp} = select i1 {cval}, {ttyp} {tval}, {etyp} {eval_}")
            return ttyp, tmp
        if isinstance(expr, Call):
            if expr.name in signatures:
                params,result=signatures[expr.name]
                if len(params) != len(expr.args): raise ValueError(f"native function '{expr.name}' expects {len(params)} argument(s)")
                vals=[]
                for arg,expected in zip(expr.args,params):
                    typ,val=emit_expr(arg,env,lines)
                    if typ != expected: raise ValueError(f"native function '{expr.name}' argument type mismatch")
                    vals.append(f"{typ} {val}")
                tmp=f"%{fresh('call')}"; lines.append(f"  {tmp} = call {result} @{expr.name}({', '.join(vals)})"); return result,tmp
            typ,val=_native_system_call_expr(expr,env,globals_out,declarations)
            if typ not in {"double","i1"}: raise ValueError(f"native function call '{expr.name}' returns unsupported type {typ}")
            return typ,val
        raise ValueError(f"native function backend does not support expression {type(expr).__name__}")

    def emit_block(body, env, lines, current_label):
        terminated=False
        for stmt in body:
            if isinstance(stmt, LetOp):
                typ,val=emit_expr(stmt.expr,env,lines); env[stmt.name]=(typ,val)
            elif isinstance(stmt, ReturnOp):
                typ,val=emit_expr(stmt.expr,env,lines); lines.append(f"  ret {typ} {val}"); terminated=True; break
            elif isinstance(stmt, IfOp):
                ctyp,cval=emit_expr(stmt.condition,env,lines)
                if ctyp != "i1": raise ValueError("native if condition must be Boolean")
                then_label=fresh("then"); else_label=fresh("else"); merge_label=fresh("merge")
                lines.append(f"  br i1 {cval}, label %{then_label}, label %{else_label}")
                lines.append(f"{then_label}:")
                then_lines=[]; then_env=dict(env); then_term=emit_block(stmt.then_body,then_env,then_lines,then_label)
                lines.extend(then_lines)
                if not then_term: lines.append(f"  br label %{merge_label}")
                lines.append(f"{else_label}:")
                else_lines=[]; else_env=dict(env); else_term=emit_block(stmt.else_body,else_env,else_lines,else_label) if stmt.else_body else False
                lines.extend(else_lines)
                if not else_term: lines.append(f"  br label %{merge_label}")
                if then_term and else_term:
                    terminated=True; break
                lines.append(f"{merge_label}:")
            elif isinstance(stmt, LocalCollectionOp):
                if stmt.source not in env or env[stmt.source][0] != "ptr":
                    raise ValueError("native collection operations currently require a List<Number> parameter or local list")
                current_type, current_value = env[stmt.source]
                owned_lists=[]
                for stage_index, (operation, expression, initial, direction) in enumerate(stmt.stages):
                    count_value = f"%{fresh('list_count')}"
                    lines.append(f"  {count_value} = call i64 @slang_number_list_count(ptr {current_value})")
                    if operation in {"map", "where"}:
                        if expression is None:
                            raise ValueError(f"Native JIT collection stage '{operation}' requires an expression")
                        if operation == "map":
                            output = f"%{fresh('mapped_list')}"
                            lines.append(f"  {output} = call ptr @slang_number_list_new(i64 {count_value})")
                        else:
                            output = f"%{fresh('filtered_list')}"
                            lines.append(f"  {output} = call ptr @slang_number_list_new(i64 0)")
                        loop_label=fresh(operation + '_loop'); body_label=fresh(operation + '_body'); done_label=fresh(operation + '_done')
                        index_phi=f"%{fresh(operation + '_index')}"; next_index=f"%{fresh(operation + '_next')}"
                        item_value=f"%{fresh(operation + '_item')}"
                        lines.append(f"  br label %{loop_label}")
                        lines.append(f"{loop_label}:")
                        lines.append(f"  {index_phi} = phi i64 [ 0, %{current_label} ], [ {next_index}, %{body_label} ]")
                        cond_name=f"%{fresh(operation + '_cond')}"
                        lines.append(f"  {cond_name} = icmp ult i64 {index_phi}, {count_value}")
                        lines.append(f"  br i1 {cond_name}, label %{body_label}, label %{done_label}")
                        lines.append(f"{body_label}:")
                        lines.append(f"  {item_value} = call double @slang_number_list_item(ptr {current_value}, i64 {index_phi})")
                        item_env=dict(env); item_env['item']=("double", item_value)
                        result_type, result_value=emit_expr(expression,item_env,lines)
                        latch_label=body_label
                        if operation == "map":
                            if result_type != "double": raise ValueError("native map expression must return Number")
                            lines.append(f"  call i32 @slang_number_list_set(ptr {output}, i64 {index_phi}, double {result_value})")
                        else:
                            if result_type != "i1": raise ValueError("native where predicate must return Boolean")
                            append_label=fresh('where_append'); continue_label=fresh('where_continue')
                            lines.append(f"  br i1 {result_value}, label %{append_label}, label %{continue_label}")
                            lines.append(f"{append_label}:")
                            lines.append(f"  call i32 @slang_number_list_append(ptr {output}, double {item_value})")
                            lines.append(f"  br label %{continue_label}")
                            lines.append(f"{continue_label}:")
                            latch_label=continue_label
                        lines.append(f"  {next_index} = add i64 {index_phi}, 1")
                        lines.append(f"  br label %{loop_label}")
                        # The loop PHI receives its back-edge value from the actual latch.
                        lines[lines.index(f"{loop_label}:")+1] = lines[lines.index(f"{loop_label}:")+1].replace(f"%{body_label} ]", f"%{latch_label} ]")
                        lines.append(f"{done_label}:")
                        current_value=output
                        owned_lists.append(output)
                        current_label=done_label
                        env[stmt.name] = ("ptr", current_value)
                        continue
                    if operation == "sort":
                        if expression is None:
                            raise ValueError("Native JIT sort requires a sort expression")
                        # The key expression is evaluated for both compared items;
                        # the list itself retains its original numeric values.
                        # Copy before sorting: the interpreter's collection sort is non-mutating.
                        sorted_copy=f"%{fresh('sorted_copy')}"
                        lines.append(f"  {sorted_copy} = call ptr @slang_number_list_new(i64 {count_value})")
                        copy_loop=fresh('sort_copy_loop'); copy_body=fresh('sort_copy_body'); copy_done=fresh('sort_copy_done')
                        copy_i=f"%{fresh('sort_copy_i')}"; copy_item=f"%{fresh('sort_copy_item')}"; copy_next=f"%{fresh('sort_copy_next')}"; copy_cond=f"%{fresh('sort_copy_cond')}"
                        lines += [f"  br label %{copy_loop}", f"{copy_loop}:", f"  {copy_i} = phi i64 [ 0, %{current_label} ], [ {copy_next}, %{copy_body} ]", f"  {copy_cond} = icmp ult i64 {copy_i}, {count_value}", f"  br i1 {copy_cond}, label %{copy_body}, label %{copy_done}", f"{copy_body}:", f"  {copy_item} = call double @slang_number_list_item(ptr {current_value}, i64 {copy_i})", f"  call i32 @slang_number_list_set(ptr {sorted_copy}, i64 {copy_i}, double {copy_item})", f"  {copy_next} = add i64 {copy_i}, 1", f"  br label %{copy_loop}", f"{copy_done}:"]
                        current_value=sorted_copy
                        owned_lists.append(sorted_copy)
                        current_label=copy_done
                        # Stable bubble sort. Equal values are never swapped.
                        outer=fresh('sort_outer'); outer_body=fresh('sort_outer_body'); outer_latch=fresh('sort_outer_latch'); outer_done=fresh('sort_outer_done')
                        inner=fresh('sort_inner'); inner_body=fresh('sort_inner_body'); inner_latch=fresh('sort_inner_latch'); inner_done=fresh('sort_inner_done')
                        i=f"%{fresh('sort_i')}"; j=f"%{fresh('sort_j')}"; jnext=f"%{fresh('sort_jnext')}"; inext=f"%{fresh('sort_inext')}"
                        cond=f"%{fresh('sort_cond')}"; inner_cond=f"%{fresh('sort_inner_cond')}"; j2=f"%{fresh('sort_j2')}"; has_next=f"%{fresh('sort_has_next')}"
                        left=f"%{fresh('sort_left')}"; right=f"%{fresh('sort_right')}"; cmp=f"%{fresh('sort_cmp')}"
                        compare_label=fresh('sort_compare'); swap_label=fresh('sort_swap'); no_swap_label=fresh('sort_no_swap')
                        lines += [f"  br label %{outer}", f"{outer}:", f"  {i} = phi i64 [ 0, %{current_label} ], [ {inext}, %{outer_latch} ]", f"  {cond} = icmp ult i64 {i}, {count_value}", f"  br i1 {cond}, label %{outer_body}, label %{outer_done}", f"{outer_body}:", f"  br label %{inner}", f"{inner}:", f"  {j} = phi i64 [ 0, %{outer_body} ], [ {jnext}, %{inner_latch} ]", f"  {j2} = add i64 {j}, 1", f"  {has_next} = icmp ult i64 {j2}, {count_value}", f"  br i1 {has_next}, label %{inner_body}, label %{inner_done}", f"{inner_body}:", f"  {left} = call double @slang_number_list_item(ptr {current_value}, i64 {j})", f"  {right} = call double @slang_number_list_item(ptr {current_value}, i64 {j2})"]
                        left_key_env=dict(env); left_key_env['item']=("double",left); left_key_type,left_key=emit_expr(expression,left_key_env,lines)
                        right_key_env=dict(env); right_key_env['item']=("double",right); right_key_type,right_key=emit_expr(expression,right_key_env,lines)
                        if left_key_type != "double" or right_key_type != "double":
                            raise ValueError("Native JIT sort key expression must return Number")
                        lines += [f"  {cmp} = fcmp {'ogt' if direction != 'desc' else 'olt'} double {left_key}, {right_key}", f"  br i1 {cmp}, label %{swap_label}, label %{no_swap_label}", f"{swap_label}:", f"  call i32 @slang_number_list_set(ptr {current_value}, i64 {j}, double {right})", f"  call i32 @slang_number_list_set(ptr {current_value}, i64 {j2}, double {left})", f"  br label %{inner_latch}", f"{no_swap_label}:", f"  br label %{inner_latch}", f"{inner_latch}:", f"  {jnext} = add i64 {j}, 1", f"  br label %{inner}", f"{inner_done}:", f"  br label %{outer_latch}", f"{outer_latch}:", f"  {inext} = add i64 {i}, 1", f"  br label %{outer}", f"{outer_done}:"]
                        current_label=outer_done
                        continue
                    if operation == "reduce":
                        if initial is None or expression is None:
                            raise ValueError("Native JIT reduce requires an initial value and reducer expression")
                        init_type, init_value=emit_expr(initial, env, lines)
                        if init_type != "double":
                            raise ValueError("Native JIT List<Number> reduce requires a Number initial accumulator")
                        loop=fresh('reduce_loop'); body_label=fresh('reduce_body'); done=fresh('reduce_done')
                        idx=f"%{fresh('reduce_index')}"; acc=f"%{fresh('reduce_acc')}"; next_idx=f"%{fresh('reduce_next_index')}"
                        item=f"%{fresh('reduce_item')}"; cond=f"%{fresh('reduce_cond')}"
                        lines += [f"  br label %{loop}", f"{loop}:", f"  {idx} = phi i64 [ 0, %{current_label} ], [ {next_idx}, %{body_label} ]", f"  {acc} = phi double [ {init_value}, %{current_label} ], [ %reduce_next_acc, %{body_label} ]", f"  {cond} = icmp ult i64 {idx}, {count_value}", f"  br i1 {cond}, label %{body_label}, label %{done}", f"{body_label}:", f"  {item} = call double @slang_number_list_item(ptr {current_value}, i64 {idx})"]
                        reducer_env=dict(env); reducer_env['item']=("double", item); reducer_env['acc']=("double", acc)
                        result_type,result_value=emit_expr(expression,reducer_env,lines)
                        if result_type != "double":
                            raise ValueError("Native JIT reduce expression must return Number")
                        lines += [f"  %reduce_next_acc = fadd double 0.00000000000000000e+00, {result_value}", f"  {next_idx} = add i64 {idx}, 1", f"  br label %{loop}", f"{done}:"]
                        env[stmt.name]=("double",acc)
                        for owned in reversed(owned_lists): lines.append(f"  call void @slang_number_list_free(ptr {owned})")
                        current_label=done
                        break
                    if operation not in {"sum", "count", "min", "max", "average", "avg", "any", "all"}:
                        raise ValueError(f"Native JIT collection stage '{operation}' is not implemented yet; use the interpreter with 'slang run'")
                    if operation == "count":
                        converted = f"%{fresh('count_number')}"
                        lines.append(f"  {converted} = uitofp i64 {count_value} to double")
                        env[stmt.name] = ("double", converted)
                        for owned in reversed(owned_lists):
                            lines.append(f"  call void @slang_number_list_free(ptr {owned})")
                        break
                    if operation in {"min", "max", "average", "avg", "any", "all"}:
                        if operation in {"any", "all"}:
                            accumulator_type = "i1"
                            initial_value = "false" if operation == "any" else "true"
                        else:
                            accumulator_type = "double"
                            initial_value = "0.00000000000000000e+00"
                        loop_label=fresh(operation + "_loop")
                        body_label=fresh(operation + "_body")
                        done_label=fresh(operation + "_done")
                        index_phi=f"%{fresh(operation + '_index')}"
                        acc_phi=f"%{fresh(operation + '_acc')}"
                        next_index=f"%{fresh(operation + '_next')}"
                        item_value=f"%{fresh(operation + '_item')}"
                        next_acc=f"%{fresh(operation + '_next_acc')}"
                        if operation in {"min", "max", "average", "avg"}:
                            guard=fresh(operation + "_guard")
                            trap_label=fresh(operation + "_empty")
                            start_label=fresh(operation + "_start")
                            declarations.append("declare void @llvm.trap()")
                            nonempty_check=f"%{fresh(operation + '_has_items')}"
                            lines.append(f"  {nonempty_check} = icmp ne i64 {count_value}, 0")
                            lines.append(f"  br i1 {nonempty_check}, label %{start_label}, label %{trap_label}")
                            lines.append(f"{trap_label}:")
                            lines.append("  call void @llvm.trap()")
                            lines.append("  unreachable")
                            lines.append(f"{start_label}:")
                            current_label=start_label
                        lines.append(f"  br label %{loop_label}")
                        lines.append(f"{loop_label}:")
                        lines.append(f"  {index_phi} = phi i64 [ 0, %{current_label} ], [ {next_index}, %{body_label} ]")
                        lines.append(f"  {acc_phi} = phi {accumulator_type} [ {initial_value}, %{current_label} ], [ {next_acc}, %{body_label} ]")
                        cond_name=f"%{fresh(operation + '_cond')}"
                        lines.append(f"  {cond_name} = icmp ult i64 {index_phi}, {count_value}")
                        lines.append(f"  br i1 {cond_name}, label %{body_label}, label %{done_label}")
                        lines.append(f"{body_label}:")
                        lines.append(f"  {item_value} = call double @slang_number_list_item(ptr {current_value}, i64 {index_phi})")
                        projected_type, projected_value = ("double", item_value) if expression is None else emit_expr(expression, {**env, "item": ("double", item_value)}, lines)
                        if operation in {"any", "all"}:
                            if projected_type == "double":
                                truth=f"%{fresh(operation + '_truth')}"
                                lines.append(f"  {truth} = fcmp one double {projected_value}, 0.00000000000000000e+00")
                                projected_value=truth
                            elif projected_type != "i1":
                                raise ValueError(f"Native JIT {operation} expression must return Boolean or Number")
                            lines.append(f"  {next_acc} = {'or' if operation == 'any' else 'and'} i1 {acc_phi}, {projected_value}")
                        elif operation in {"min", "max"}:
                            if projected_type != "double": raise ValueError(f"Native JIT {operation} expression must return Number")
                            cmp=f"%{fresh(operation + '_cmp')}"
                            lines.append(f"  {cmp} = fcmp {'olt' if operation == 'min' else 'ogt'} double {projected_value}, {acc_phi}")
                            first=f"%{fresh(operation + '_first')}"
                            choose=f"%{fresh(operation + '_choose')}"
                            lines.append(f"  {first} = icmp eq i64 {index_phi}, 0")
                            lines.append(f"  {choose} = or i1 {first}, {cmp}")
                            lines.append(f"  {next_acc} = select i1 {choose}, double {projected_value}, double {acc_phi}")
                        else:
                            if projected_type != "double": raise ValueError(f"Native JIT {operation} expression must return Number")
                            lines.append(f"  {next_acc} = fadd double {acc_phi}, {projected_value}")
                        lines.append(f"  {next_index} = add i64 {index_phi}, 1")
                        lines.append(f"  br label %{loop_label}")
                        lines.append(f"{done_label}:")
                        if operation in {"average", "avg"}:
                            nonempty=f"%{fresh('avg_nonempty')}"
                            converted=f"%{fresh('avg_count')}"
                            result=f"%{fresh('avg_result')}"
                            lines.append(f"  {nonempty} = icmp ne i64 {count_value}, 0")
                            lines.append(f"  {converted} = uitofp i64 {count_value} to double")
                            lines.append(f"  {result} = fdiv double {acc_phi}, {converted}")
                            env[stmt.name] = ("double", result)
                        elif operation in {"any", "all"}:
                            env[stmt.name] = ("i1", acc_phi)
                        else:
                            env[stmt.name] = ("double", acc_phi)
                        for owned in reversed(owned_lists):
                            lines.append(f"  call void @slang_number_list_free(ptr {owned})")
                        current_label=done_label
                        break
                    loop_label=fresh("sum_loop"); body_label=fresh("sum_body"); done_label=fresh("sum_done")
                    index_phi=f"%{fresh('sum_index')}"; total_phi=f"%{fresh('sum_total')}"
                    next_index=f"%{fresh('sum_next')}"; item_value=f"%{fresh('sum_item')}"; next_total=f"%{fresh('sum_acc')}"
                    lines.append(f"  br label %{loop_label}")
                    lines.append(f"{loop_label}:")
                    lines.append(f"  {index_phi} = phi i64 [ 0, %{current_label} ], [ {next_index}, %{body_label} ]")
                    lines.append(f"  {total_phi} = phi double [ 0.00000000000000000e+00, %{current_label} ], [ {next_total}, %{body_label} ]")
                    cond_name=f"%{fresh('sum_cond')}"
                    lines.append(f"  {cond_name} = icmp ult i64 {index_phi}, {count_value}")
                    lines.append(f"  br i1 {cond_name}, label %{body_label}, label %{done_label}")
                    lines.append(f"{body_label}:")
                    lines.append(f"  {item_value} = call double @slang_number_list_item(ptr {current_value}, i64 {index_phi})")
                    projected_type, projected_value = ("double", item_value) if expression is None else emit_expr(expression, {**env, "item": ("double", item_value)}, lines)
                    if projected_type != "double": raise ValueError("Native JIT sum expression must return Number")
                    lines.append(f"  {next_total} = fadd double {total_phi}, {projected_value}")
                    lines.append(f"  {next_index} = add i64 {index_phi}, 1")
                    lines.append(f"  br label %{loop_label}")
                    lines.append(f"{done_label}:")
                    env[stmt.name] = ("double", total_phi)
                    for owned in reversed(owned_lists):
                        lines.append(f"  call void @slang_number_list_free(ptr {owned})")
                    current_label=done_label
            else:
                raise ValueError(f"native function backend does not support statement {type(stmt).__name__}")
        return terminated

    for fn in p.ast.functions:
        params,result=signatures[fn.name]
        lines=[f"define {result} @{fn.name}({', '.join(f'{t} %{name}' for (name,_),t in zip(fn.parameters,params))}) {{", "entry:"]
        env={name:(typ,f"%{name}") for (name,_),typ in zip(fn.parameters,params)}
        terminated=emit_block(fn.body,env,lines,"entry")
        if not terminated:
            raise ValueError(f"native function '{fn.name}' does not return on every native path")
        lines.append("}")
        function_blocks.append(lines)

    decls=[]; seen=set()
    for d in declarations:
        if d.startswith('declare ') and d not in seen: seen.add(d); decls.append(d)
    out=[]
    for name,encoded,length in globals_out: out.append(f"@{name} = private constant [{length} x i8] c\"{encoded}\"")
    out.extend(decls)
    for fn in p.ast.functions: out.append(f"declare {signatures[fn.name][1]} @{fn.name}({', '.join(signatures[fn.name][0])})") if False else None
    for block in function_blocks: out.extend(block); out.append("")
    return out, signatures



def _sequence_numeric_expr(expr, current_value, serial, lines):
    """Lower the restricted numeric recurrence used by native sequence-f64."""
    if isinstance(expr, Literal) and isinstance(expr.value, (int, float)) and not isinstance(expr.value, bool):
        return f"{float(expr.value):.17e}"
    if isinstance(expr, Name) and expr.name == "value":
        return current_value
    if isinstance(expr, Binary) and expr.op in {"+", "-", "*", "/", "^", "%"}:
        left = _sequence_numeric_expr(expr.left, current_value, serial, lines)
        right = _sequence_numeric_expr(expr.right, current_value, serial, lines)
        out = f"%seq_expr_{serial}_{len(lines)}"
        if expr.op == "^":
            lines.append(f"  {out} = call double @llvm.pow.f64(double {left}, double {right})")
        else:
            op = {"+": "fadd", "-": "fsub", "*": "fmul", "/": "fdiv", "%": "frem"}[expr.op]
            lines.append(f"  {out} = {op} double {left}, {right}")
        return out
    raise ValueError("native sequence backend supports numeric literals, value, and arithmetic recurrence")


def sequence_llvm_ir(p: Program):
    """Lower one numeric fixed-length sequence, optionally followed by reduce."""
    if len(p.ast.sequences) != 1:
        raise ValueError("native sequence backend currently requires exactly one sequence")
    seq = p.ast.sequences[0]
    if seq.until is not None or seq.target is not None:
        raise ValueError("native sequence backend currently supports fixed-length numeric sequences only")
    if not isinstance(seq.initial, Literal) or not isinstance(seq.initial.value, (int, float)) or isinstance(seq.initial.value, bool):
        raise ValueError("native sequence backend requires a numeric literal initial value")
    if not isinstance(seq.expr, (Name, Literal, Binary)):
        raise ValueError("native sequence backend requires a numeric recurrence expression")
    if any(r.source != seq.result for r in p.ast.reduces):
        raise ValueError("native sequence reduce must consume the sequence result")
    if len(p.ast.reduces) > 1:
        raise ValueError("native sequence backend supports at most one reduce")
    if p.ast.filters or p.ast.maps or p.ast.sorts or p.ast.aggregates or p.ast.functions or p.ast.goals or p.ast.path_goals or p.ast.satisfy_goals or p.bodies or p.simulation:
        raise ValueError("native sequence backend currently accepts only sequence and optional reduce")

    steps = seq.steps
    cap = max(1, steps)
    initial = float(seq.initial.value)
    lines = [
        "; ModuleID = 'slang-sequence-f64'",
        'source_filename = "slang"',
        '',
        'declare i32 @printf(ptr, ...)', 'declare i32 @strcmp(ptr, ptr)',
        'declare double @llvm.pow.f64(double, double)',
        '@fmt_num = private constant [7 x i8] c"%.15g\\0A\\00"',
        'define i32 @main() {',
        'entry:',
        f'  %seq_buf = alloca [{cap} x double]',
        '  br label %seq_loop',
        'seq_loop:',
        '  %seq_i = phi i64 [ 0, %entry ], [ %seq_next, %seq_body ]',
        f'  %seq_value = phi double [ {initial:.17e}, %entry ], [ %seq_next_value, %seq_body ]',
        f'  %seq_cond = icmp ult i64 %seq_i, {steps}',
        '  br i1 %seq_cond, label %seq_body, label %seq_done',
        'seq_body:',
        '  %seq_dst = getelementptr [' + str(cap) + ' x double], ptr %seq_buf, i64 0, i64 %seq_i',
        '  store double %seq_value, ptr %seq_dst',
    ]
    next_value = _sequence_numeric_expr(seq.expr, "%seq_value", 0, lines)
    lines += [
        f'  %seq_next_value = fadd double {next_value}, 0.0',
        '  %seq_next = add i64 %seq_i, 1',
        '  br label %seq_loop',
        'seq_done:',
    ]

    reduce_name = None
    if p.ast.reduces:
        red = p.ast.reduces[0]
        if not isinstance(red.initial, Literal) or not isinstance(red.initial.value, (int, float)) or isinstance(red.initial.value, bool):
            raise ValueError("native sequence reduce requires a numeric literal initial accumulator")
        if not isinstance(red.expr, Binary) or not isinstance(red.expr.left, Name) or red.expr.left.name != "acc" or not isinstance(red.expr.right, Name) or red.expr.right.name != "item" or red.expr.op not in {"+", "-", "*", "/", "^"}:
            raise ValueError("native sequence reduce supports acc <+|-|*|/> item")
        reduce_name = red.result
        lines += [
            '  %red_acc = alloca double',
            f'  store double {float(red.initial.value):.17e}, ptr %red_acc',
            '  br label %red_loop',
            'red_loop:',
            '  %red_i = phi i64 [ 0, %seq_done ], [ %red_next, %red_body ]',
            f'  %red_cond = icmp ult i64 %red_i, {steps}',
            '  br i1 %red_cond, label %red_body, label %red_done',
            'red_body:',
            '  %red_item_ptr = getelementptr [' + str(cap) + ' x double], ptr %seq_buf, i64 0, i64 %red_i',
            '  %red_item = load double, ptr %red_item_ptr',
            '  %red_old = load double, ptr %red_acc',
        ]
        red_op = {"+": "fadd", "-": "fsub", "*": "fmul", "/": "fdiv"}[red.expr.op]
        lines += [f'  %red_new = {red_op} double %red_old, %red_item', '  store double %red_new, ptr %red_acc', '  %red_next = add i64 %red_i, 1', '  br label %red_loop', 'red_done:', '  %red_result = load double, ptr %red_acc']

    show_names = {x.name for x in (p.show_exprs or []) if isinstance(x, Name)}
    if not show_names:
        show_names = {name for name, _field in p.shows}
    if seq.result in show_names:
        lines += [
            '  br label %show_loop',
            'show_loop:',
            '  %show_i = phi i64 [ 0, %red_done ], [ %show_next, %show_body ]' if reduce_name else '  %show_i = phi i64 [ 0, %seq_done ], [ %show_next, %show_body ]',
            f'  %show_cond = icmp ult i64 %show_i, {steps}',
            '  br i1 %show_cond, label %show_body, label %show_done',
            'show_body:',
            f'  %show_ptr = getelementptr [{cap} x double], ptr %seq_buf, i64 0, i64 %show_i',
            '  %show_value = load double, ptr %show_ptr',
            '  call i32 (ptr, ...) @printf(ptr @fmt_num, double %show_value)',
            '  %show_next = add i64 %show_i, 1',
            '  br label %show_loop',
            'show_done:',
        ]
    if reduce_name and reduce_name in show_names:
        lines += ['  call i32 (ptr, ...) @printf(ptr @fmt_num, double %red_result)']
    lines += ['  ret i32 0', '}']
    return '\n'.join(lines)


def native_program_llvm_ir(p: Program, schema_contract=None):
    """Lower a scalar program containing explicitly typed user functions."""
    validate(p)
    if p.ast.filters or p.ast.maps or p.ast.sorts or p.ast.aggregates or p.ast.reduces:
        if p.ast.sequences or p.ast.goals or p.ast.path_goals or p.ast.satisfy_goals or p.bodies or p.simulation:
            raise ValueError("native function+collection backend currently accepts data/filter/map/sort/reduce/aggregate programs")
        function_part, signatures = _native_function_llvm_ir(p)
        if p.ast.reduces:
            if p.ast.sorts:
                return pipeline_sort_reduce_llvm_ir(p, function_part=function_part, signatures=signatures)
            if p.ast.aggregates:
                raise ValueError("native function collection backend does not combine reduce and aggregate in one terminal")
            return fused_reduce_llvm_ir(p)
        if p.ast.aggregates:
            # The fused filter/map aggregate backend intentionally excludes sort.
            # Once a sort is present, use the general aggregate lowering so the
            # sort remains an explicit stage and user-function expressions can
            # still be lowered through the ordinary scalar expression emitter.
            if p.ast.sorts:
                return aggregate_llvm_ir(p, function_part=function_part, signatures=signatures, schema_contract=schema_contract)
            if function_part:
                return fused_aggregate_llvm_ir(p, function_part=function_part, signatures=signatures)
            if all(item.source in (p.data_tables or {}) for item in p.ast.aggregates):
                return aggregate_llvm_ir(p, function_part=function_part, signatures=signatures, schema_contract=schema_contract)
            return fused_aggregate_llvm_ir(p, function_part=function_part, signatures=signatures)
        if p.ast.sorts:
            return sort_llvm_ir(p, function_part=function_part, signatures=signatures)
        return collection_llvm_ir(p, function_part=function_part, signatures=signatures, schema_contract=schema_contract)
    if p.ast.sequences:
        return sequence_llvm_ir(p)
    if p.ast.sorts or p.ast.aggregates or p.ast.reduces or p.ast.sequences or p.ast.goals or p.ast.path_goals or p.ast.satisfy_goals or p.bodies or p.simulation:
        raise ValueError("native function backend currently accepts scalar functions and top-level scalar bindings/show expressions")
    function_part, signatures = _native_function_llvm_ir(p)
    env={}; globals_out=[]; declarations=[]
    for binding in p.ast.bindings:
        typ,value=_native_system_call_expr(binding.expr,env,globals_out,declarations,signatures)
        env[binding.name]=(typ,value)
    # Re-evaluate user-function calls through the ordinary emitter is avoided by
    # temporarily extending the expression helper with a small call lowering.
    def top_expr(expr):
        if isinstance(expr, Call) and expr.name in signatures:
            params,result=signatures[expr.name]
            if len(params)!=len(expr.args): raise ValueError(f"native function '{expr.name}' expects {len(params)} argument(s)")
            args=[]
            for arg,expected in zip(expr.args,params):
                typ,val=_native_system_call_expr(arg,env,globals_out,declarations,signatures)
                if typ!=expected: raise ValueError(f"native function '{expr.name}' argument type mismatch")
                args.append(f"{typ} {val}")
            tmp=f"%top_call_{len(declarations)}"; declarations.append(f"  {tmp} = call {result} @{expr.name}({', '.join(args)})"); return result,tmp
        return _native_system_call_expr(expr,env,globals_out,declarations,signatures)
    show_values=[top_expr(expr) for expr in p.show_exprs]
    seen=set(); declarations=[x for x in declarations if not (x in seen or seen.add(x))]
    lines=["; ModuleID = 'slang-native-functions'", 'source_filename = "slang"', '']
    lines.extend(function_part or [])
    lines += ['declare i32 @printf(ptr, ...)', 'declare i64 @slang_text_list_count(ptr)', 'declare ptr @slang_text_list_item(ptr, i64)', 'declare void @slang_text_free(ptr)', 'declare void @slang_text_list_free(ptr)', '']
    for d in declarations:
        if d.startswith('declare '): lines.append(d)
    lines += ['define i32 @main(i32 %argc, ptr %argv) {', 'entry:']
    for d in declarations:
        if not d.startswith('declare '): lines.append(d)
    for index,(typ,value) in enumerate(show_values):
        if typ=='double':
            name=f"fmt_num_{index}"; lines.insert(2,f"@{name} = private constant [7 x i8] c\"%.15g\\0A\\00\""); lines.append(f"  %show_{index} = call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([7 x i8], ptr @{name}, i64 0, i64 0), double {value})")
        elif typ=='i1':
            fmt=f"fmt_bool_{index}"; tr=f"bool_true_{index}"; fa=f"bool_false_{index}"; lines.insert(2,f"@{fmt} = private constant [4 x i8] c\"%s\\0A\\00\""); lines.insert(2,f"@{tr} = private constant [5 x i8] c\"true\\00\""); lines.insert(2,f"@{fa} = private constant [6 x i8] c\"false\\00\""); ptr=f"%show_bool_ptr_{index}"; lines.append(f"  {ptr} = select i1 {value}, ptr getelementptr inbounds ([5 x i8], ptr @{tr}, i64 0, i64 0), ptr getelementptr inbounds ([6 x i8], ptr @{fa}, i64 0, i64 0)"); lines.append(f"  %show_{index} = call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([4 x i8], ptr @{fmt}, i64 0, i64 0), ptr {ptr})")
        elif typ=='ptr':
            fmt=f"fmt_text_{index}"; lines.insert(2,f"@{fmt} = private constant [4 x i8] c\"%s\0A\00\""); lines.append(f"  %show_{index} = call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([4 x i8], ptr @{fmt}, i64 0, i64 0), ptr {value})"); lines.append(f"  call void @slang_text_free(ptr {value})")
        else: raise ValueError(f"cannot show native value of type {typ}")
    lines += ['  ret i32 0', '}', '']
    return '\n'.join(lines)


def _native_entity_llvm_ir(p: Program):
    """Lower a small immutable user-entity subset to native LLVM.

    Entity fields are stored as numeric values together with their declared
    S-Lang unit names. Computed properties currently accept a direct
    ``return self.<field>`` body, which is enough to make the entity control
    benchmark genuinely native without introducing a second object runtime.
    """
    validate(p)
    if not p.ast.entities:
        raise ValueError("native entity backend requires an entity declaration")
    if p.ast.records or p.ast.functions or p.ast.filters or p.ast.maps or p.ast.sorts or p.ast.aggregates or p.ast.reduces:
        raise ValueError("native entity backend currently accepts scalar entity bindings and projections")
    if p.bodies or p.simulation or p.ast.sequences or p.ast.goals or p.ast.path_goals or p.ast.satisfy_goals:
        raise ValueError("native entity backend accepts scalar entity bindings only")

    entities = {e.name: e for e in p.ast.entities}
    bindings = {}
    for b in p.ast.bindings:
        if not isinstance(b.expr, Call) or b.expr.name not in entities:
            raise ValueError("native entity backend requires entity constructor bindings")
        decl = entities[b.expr.name]
        if len(b.expr.args) != len(decl.fields):
            raise ValueError(f"entity '{decl.name}' expects {len(decl.fields)} field value(s)")
        bindings[b.name] = (decl.name, b.expr)

    props = {(x.entity_type, x.name): x for x in p.ast.properties}
    lines = ["; ModuleID = 'slang-entities'", 'source_filename = "slang"', '']
    lines += ['declare i32 @printf(ptr, ...)', '']
    globals_out = []
    env = {}
    counter = [0]

    def fresh(prefix):
        n = counter[0]; counter[0] += 1
        return f"%{prefix}_{n}"

    def c_string(text):
        return _llvm_c_string(text)

    def emit_quantity(expr, expected_unit=None):
        if not isinstance(expr, Literal) or not isinstance(expr.value, Quantity):
            raise ValueError("native entity backend requires quantity literals")
        q = expr.value
        if expected_unit is not None and q.unit != expected_unit:
            raise ValueError(f"entity field requires unit '{expected_unit}', got '{q.unit}'")
        return f"{float(q.value):.17e}", q.unit

    for name, expr in bindings.values():
        decl = entities[name]
        values = {}
        for (fname, tref), arg in zip(decl.fields, expr.args):
            if tref.name not in UNIT_DIM:
                raise ValueError(f"native entity backend currently supports quantity fields only, got '{tref.name}'")
            values[fname] = emit_quantity(arg, tref.name)
        env_key = next(k for k, v in bindings.items() if v == (name, expr))
        env[env_key] = (name, values)

    def field_value(entity_name, entity_values, field):
        if field not in entity_values:
            raise ValueError(f"unknown field '{field}' on entity '{entity_name}'")
        return entity_values[field]

    def show_expr(expr):
        if not isinstance(expr, Property) or not isinstance(expr.base, Name):
            raise ValueError("native entity backend supports entity property projections only")
        if expr.base.name not in env:
            raise ValueError(f"native entity backend cannot resolve '{expr.base.name}'")
        entity_name, values = env[expr.base.name]
        if expr.name in values:
            return field_value(entity_name, values, expr.name)
        prop = props.get((entity_name, expr.name))
        if prop is None:
            raise ValueError(f"unknown entity property '{entity_name}.{expr.name}'")
        if len(prop.body) != 1 or not isinstance(prop.body[0], ReturnOp) or not isinstance(prop.body[0].expr, Property):
            raise ValueError("native entity backend supports direct field-return properties")
        base = prop.body[0].expr.base
        if not isinstance(base, Name) or base.name != 'self':
            raise ValueError("native entity property must return self.<field>")
        return field_value(entity_name, values, prop.body[0].expr.name)

    shows = [show_expr(x) for x in p.show_exprs]
    for i, (value, unit) in enumerate(shows):
        key = f"unit_{i}"; encoded, length = c_string(unit)
        globals_out.append((key, encoded, length))
        lines.append(f"@{key} = private constant [{length} x i8] c\"{encoded}\"")
    lines.append('')
    lines.append('define i32 @main(i32 %argc, ptr %argv) {')
    lines.append('entry:')
    for i, (value, unit) in enumerate(shows):
        fmt_key = f"fmt_{i}"; fmt = "%.15g %s\n\x00"; encoded, length = c_string(fmt)
        lines.append(f"@{fmt_key} = private constant [{length} x i8] c\"{encoded}\"")
        # LLVM globals cannot be emitted inside a function; the format globals
        # are moved to the module below after all show expressions are known.
        lines.pop()
    fmt_len = len("%.15g %s\n".encode()) + 1
    for i, (value, unit) in enumerate(shows):
        fmt_key = f"fmt_{i}"
        unit_key = f"unit_{i}"
        lines.append(f"  %show_{i} = call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([{fmt_len} x i8], ptr @{fmt_key}, i64 0, i64 0), double {value}, ptr getelementptr inbounds ([{len(unit.encode('utf-8')) + 1} x i8], ptr @{unit_key}, i64 0, i64 0))")
    lines += ['  ret i32 0', '}', '']
    # Insert format globals before the declarations/function body.
    globals_text=[]
    for i in range(len(shows)):
        fmt_key=f"fmt_{i}"; encoded,length=c_string("%.15g %s\n\x00")
        globals_text.append(f"@{fmt_key} = private constant [{length} x i8] c\"{encoded}\"")
    # The initial declaration list has the C runtime declaration; prepend all
    # generated globals after the source filename for valid module ordering.
    head=lines[:2] + globals_text + [""] + lines[2:]
    return '\n'.join(head)


def _native_circle_llvm_ir(p: Program):
    """Lower built-in Circle values and their derived geometry properties."""
    validate(p)
    if not p.circles or p.ast.entities or p.ast.records or p.ast.functions or p.ast.bindings:
        raise ValueError("native circle backend currently accepts standalone circle declarations")
    if p.ast.filters or p.ast.maps or p.ast.sorts or p.ast.aggregates or p.ast.reduces or p.ast.sequences:
        raise ValueError("native circle backend accepts standalone circle declarations")
    circles = {c.name: c for c in p.circles}
    shows=[]
    for expr in p.show_exprs:
        if not isinstance(expr, Property) or not isinstance(expr.base, Name) or expr.base.name not in circles:
            raise ValueError("native circle backend supports circle property projections only")
        c=circles[expr.base.name]
        r=c.radius.value
        if expr.name == 'radius': value=r; unit='m'
        elif expr.name == 'area': value=math.pi*r*r; unit='m2'
        elif expr.name == 'circumference': value=2*math.pi*r; unit='m'
        else: raise ValueError(f"unknown circle property '{expr.name}'")
        shows.append((value,unit))
    lines=["; ModuleID = 'slang-circles'", 'source_filename = "slang"', '', 'declare i32 @printf(ptr, ...)', '']
    for i,(_,unit) in enumerate(shows):
        def cs(text):
            return _llvm_c_string(text)
        esc,n=cs(unit); lines.append(f"@unit_{i} = private constant [{n} x i8] c\"{esc}\"")
        esc,n=cs("%.15g %s\n\x00"); lines.append(f"@fmt_{i} = private constant [{n} x i8] c\"{esc}\"")
    lines += ['', 'define i32 @main(i32 %argc, ptr %argv) {', 'entry:']
    fmt_len = len("%.15g %s\n".encode()) + 1
    for i,(value,unit) in enumerate(shows):
        lines.append(f"  %show_{i} = call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([{fmt_len} x i8], ptr @fmt_{i}, i64 0, i64 0), double {float(value):.17e}, ptr getelementptr inbounds ([{len(unit.encode())+1} x i8], ptr @unit_{i}, i64 0, i64 0))")
    lines += ['  ret i32 0', '}', '']
    return '\n'.join(lines)


def native_csv_sort_llvm_ir(p: Program):
    """Lower a materialized ``read_csv -> sort -> show`` pipeline.

    CSV fields are Text, so the observable sort order is stable lexical order
    of the selected field.  The runtime materializes only row indices, then
    prints the sorted records without creating Python RecordValue objects.
    """
    validate(p)
    if p.bodies or p.simulation or p.ast.filters or p.ast.maps or p.ast.aggregates or p.ast.reduces or p.ast.sequences:
        raise ValueError("native CSV sort currently supports a direct read_csv -> sort -> show pipeline")
    if len(p.ast.sorts) != 1 or len(p.ast.bindings) != 1 or len(p.show_exprs) != 1:
        raise ValueError("native CSV sort requires one source, one sort and one direct show")
    sort = p.ast.sorts[0]
    source_binding = next((b for b in p.ast.bindings if isinstance(b.expr, Call) and b.expr.name == "read_csv"), None)
    if source_binding is None or not isinstance(source_binding.expr.args[0], Literal) or not isinstance(source_binding.expr.args[0].value, str):
        raise ValueError("native CSV sort requires a literal read_csv path")
    if sort.source != source_binding.name or not isinstance(p.show_exprs[0], Name) or p.show_exprs[0].name != sort.result:
        raise ValueError("native CSV sort requires showing the sorted result directly")
    expr = sort.spec.expr
    if not isinstance(expr, (Field, Property)) or not isinstance(expr.base, Name) or expr.base.name not in {"row", "item"}:
        raise ValueError("native CSV sort requires a direct row/item field")
    field = expr.name
    path_enc, path_len = _llvm_c_string(source_binding.expr.args[0].value)
    field_enc, field_len = _llvm_c_string(field)
    lines = [
        "; ModuleID = 'slang-native-csv-sort'", 'source_filename = "slang"',
        f'@csv_path = private constant [{path_len} x i8] c"{path_enc}"',
        f'@csv_field = private constant [{field_len} x i8] c"{field_enc}"', '',
        'declare i64 @slang_csv_open(ptr)',
        'declare i64 @slang_csv_field_index(i64, ptr)',
        'declare i32 @slang_csv_sort_print(i64, i64, i32)',
        'declare void @slang_csv_free(i64)', '',
        'define i32 @main() {', 'entry:',
        f'  %csv = call i64 @slang_csv_open(ptr getelementptr inbounds ([{path_len} x i8], ptr @csv_path, i64 0, i64 0))',
        f'  %field = call i64 @slang_csv_field_index(i64 %csv, ptr getelementptr inbounds ([{field_len} x i8], ptr @csv_field, i64 0, i64 0))',
        f'  %status = call i32 @slang_csv_sort_print(i64 %csv, i64 %field, i32 {1 if sort.spec.ascending else 0})',
        '  call void @slang_csv_free(i64 %csv)',
        '  ret i32 %status', '}', ''
    ]
    return '\n'.join(lines)

def native_csv_group_multi_aggregate_llvm_ir(p: Program):
    """Lower multiple grouped aggregates sharing one CSV traversal."""
    validate(p)
    if p.ast.sorts or p.ast.reduces or p.ast.sequences:
        raise ValueError("native CSV multi-group aggregate does not support sort/reduce/sequence")
    group_names = {"group_count", "group_sum", "group_average", "group_min", "group_max"}
    calls = [b for b in p.ast.bindings if isinstance(b.expr, Call) and b.expr.name in group_names]
    if len(calls) < 2:
        raise ValueError("native CSV multi-group aggregate requires at least two grouped aggregate bindings")
    if not p.show_exprs or any(not isinstance(x, Name) or x.name not in {b.name for b in calls} for x in p.show_exprs):
        raise ValueError("native CSV multi-group aggregate requires showing grouped aggregate results directly")
    from .execution_ir import build_execution_ir
    from .pipeline_ir import build_pipeline_ir
    pipelines = [build_pipeline_ir(build_execution_ir(p.ast), b.name) for b in calls]
    if any("group" not in x.kinds for x in pipelines):
        raise ValueError("native CSV multi-group aggregate requires group pipeline stages")
    roots = {x.source for x in pipelines}
    if len(roots) != 1:
        raise ValueError("native CSV multi-group aggregate requires one shared source")
    root_name = next(iter(roots))
    source_binding = next((b for b in p.ast.bindings if b.name == root_name), None)
    if source_binding is None or not (isinstance(source_binding.expr, Call) and source_binding.expr.name == "read_csv"):
        raise ValueError("native CSV multi-group aggregate requires a read_csv root source")
    if len(source_binding.expr.args) != 1 or not isinstance(source_binding.expr.args[0], Literal) or not isinstance(source_binding.expr.args[0].value, str):
        raise ValueError("native CSV multi-group aggregate requires a literal read_csv path")
    group_fields = []
    value_fields = []
    ops = []
    shared_map = None
    shared_group_field = None
    for b in calls:
        call = b.expr
        if len(call.args) < 2 or not all(isinstance(x, Literal) and isinstance(x.value, str) for x in call.args[1:]):
            raise ValueError(f"native {call.name} requires literal group/value fields")
        gf = call.args[1].value
        if shared_group_field is None: shared_group_field = gf
        if gf != shared_group_field:
            raise ValueError("native CSV multi-group aggregate requires one shared group field")
        if call.name == "group_count":
            value_fields.append(gf); ops.append(0)
            continue
        if len(call.args) != 3:
            raise ValueError(f"native {call.name} requires a value field")
        map_stages = [stage for stage in pipelines[calls.index(b)].stages if stage.kind == "map"]
        if len(map_stages) != 1:
            raise ValueError(f"native {call.name} requires one explicit numeric record map")
        map_op = next((m for m in p.ast.maps if m.result == map_stages[0].result), None)
        if map_op is None or not isinstance(map_op.expr, Call) or not map_op.expr.args:
            raise ValueError(f"native {call.name} requires a record-constructor map")
        ctor = map_op.expr
        record = next((r for r in p.ast.records if r.name == ctor.name), None)
        if record is None:
            raise ValueError(f"native {call.name} requires a declared record constructor")
        field_exprs = dict(zip((f[0] for f in record.fields), ctor.args))
        key_expr = field_exprs.get(gf)
        vf = call.args[2].value
        value_expr = field_exprs.get(vf)
        if not (isinstance(key_expr, (Field, Property)) and isinstance(key_expr.base, Name) and key_expr.base.name in {"row", "item"} and key_expr.name == gf):
            raise ValueError(f"native {call.name} requires direct group-key field preservation")
        if not (isinstance(value_expr, Call) and value_expr.name == "to_number" and len(value_expr.args) == 1):
            raise ValueError(f"native {call.name} requires explicit to_number(value) in the mapped record")
        numeric_expr = value_expr.args[0]
        if not (isinstance(numeric_expr, (Field, Property)) and isinstance(numeric_expr.base, Name) and numeric_expr.base.name in {"row", "item"} and numeric_expr.name == vf):
            raise ValueError(f"native {call.name} requires direct to_number(row.field)")
        value_fields.append(vf); ops.append({"group_sum": 1, "group_average": 2, "group_min": 3, "group_max": 4}[call.name])
    if shared_group_field is None:
        raise ValueError("native CSV multi-group aggregate requires a group field")
    # All filters must be identical and direct text equality; they are applied
    # once by the shared runtime traversal.
    filter_stages = [stage for stage in pipelines[0].stages if stage.kind == "filter"]
    filters = [f for f in p.ast.filters if any(stage.result == f.result for stage in filter_stages)]
    if len(filters) > 1:
        raise ValueError("native CSV multi-group aggregate supports at most one direct text filter")
    filter_field = filter_value = None
    if filters:
        expr = filters[0].predicate.expr
        if not isinstance(expr, Compare) or expr.op != "==" or not isinstance(expr.left, (Field, Property)) or not isinstance(expr.left.base, Name) or expr.left.base.name not in {"row", "item"} or not isinstance(expr.right, Literal) or not isinstance(expr.right.value, str):
            raise ValueError("native CSV multi-group aggregate filter requires field == text literal")
        filter_field, filter_value = expr.left.name, expr.right.value
        for pipe in pipelines[1:]:
            other = [f for f in p.ast.filters if any(stage.result == f.result for stage in pipe.stages)]
            if len(other) != 1 or other[0].predicate.expr != expr:
                raise ValueError("native CSV multi-group aggregate requires one shared filter")
    path_enc, path_len = _llvm_c_string(source_binding.expr.args[0].value)
    group_enc, group_len = _llvm_c_string(shared_group_field)
    value_names = []
    for vf in value_fields:
        value_names.append(_llvm_c_string(vf))
    value_ptrs = ', '.join(f'ptr getelementptr inbounds ([{ln} x i8], ptr @value_{i}, i64 0, i64 0)' for i, (_, ln) in enumerate(value_names))
    field_array = ', '.join(f'i64 {0}' for _ in value_fields)
    lines = [
        "; ModuleID = 'slang-native-csv-group-multi'", 'source_filename = "slang"',
        f'@csv_path = private constant [{path_len} x i8] c"{path_enc}"',
        f'@group_name = private constant [{group_len} x i8] c"{group_enc}"',
    ]
    for i,(enc,ln) in enumerate(value_names): lines.append(f'@value_{i} = private constant [{ln} x i8] c"{enc}"')
    if filter_field is not None:
        ff_enc, ff_len = _llvm_c_string(filter_field); fv_enc, fv_len = _llvm_c_string(filter_value)
        lines += [f'@filter_name = private constant [{ff_len} x i8] c"{ff_enc}"', f'@filter_value = private constant [{fv_len} x i8] c"{fv_enc}"']
    lines += ['', 'declare i64 @slang_csv_open(ptr)', 'declare i64 @slang_csv_field_index(i64, ptr)',
              'declare i32 @slang_csv_group_multi_numeric_print(i64, i64, ptr, ptr, i64, i64, ptr)', 'declare void @slang_csv_free(i64)',
              'define i32 @main() {', 'entry:',
              f'  %csv = call i64 @slang_csv_open(ptr getelementptr inbounds ([{path_len} x i8], ptr @csv_path, i64 0, i64 0))',
              f'  %group_field = call i64 @slang_csv_field_index(i64 %csv, ptr getelementptr inbounds ([{group_len} x i8], ptr @group_name, i64 0, i64 0))']
    # Use fixed-size stack arrays for up to 16 aggregate specs.
    lines += ['  %value_fields = alloca i64, i64 16', '  %ops = alloca i32, i64 16']
    for i, vf in enumerate(value_fields):
        lines.append(f'  %vf_{i} = call i64 @slang_csv_field_index(i64 %csv, ptr getelementptr inbounds ([{value_names[i][1]} x i8], ptr @value_{i}, i64 0, i64 0))')
        lines.append(f'  %vf_ptr_{i} = getelementptr i64, ptr %value_fields, i64 {i}')
        lines.append(f'  store i64 %vf_{i}, ptr %vf_ptr_{i}')
        lines.append(f'  %op_ptr_{i} = getelementptr i32, ptr %ops, i64 {i}')
        lines.append(f'  store i32 {ops[i]}, ptr %op_ptr_{i}')
    if filter_field is not None:
        lines.append(f'  %filter_field = call i64 @slang_csv_field_index(i64 %csv, ptr getelementptr inbounds ([{ff_len} x i8], ptr @filter_name, i64 0, i64 0))')
        lines.append(f'  %status = call i32 @slang_csv_group_multi_numeric_print(i64 %csv, i64 %group_field, ptr %value_fields, ptr %ops, i64 {len(ops)}, i64 %filter_field, ptr getelementptr inbounds ([{fv_len} x i8], ptr @filter_value, i64 0, i64 0))')
    else:
        lines.append(f'  %status = call i32 @slang_csv_group_multi_numeric_print(i64 %csv, i64 %group_field, ptr %value_fields, ptr %ops, i64 {len(ops)}, i64 -1, ptr null)')
    lines += ['  call void @slang_csv_free(i64 %csv)', '  ret i32 %status', '}', '']
    return '\n'.join(lines)

def native_csv_group_aggregate_llvm_ir(p: Program):
    """Lower a small, semantically explicit grouped CSV subset.

    ``group_count(read_csv(...), key)`` is always supported.  A preceding
    filter is supported when it is a direct ``row.field == "literal"`` text
    comparison; the runtime then performs the same equality and stable
    first-seen grouping semantics without materializing Python records.
    """
    validate(p)
    if p.ast.sorts or p.ast.reduces or p.ast.sequences:
        raise ValueError("native CSV group aggregate supports group_count or explicit numeric grouped aggregates")
    if len(p.ast.bindings) < 2 or len(p.show_exprs) != 1:
        raise ValueError("native CSV group aggregate requires source, result and direct show")
    call_binding = next((b for b in p.ast.bindings if isinstance(b.expr, Call) and b.expr.name in {"group_count", "group_sum", "group_average"}), None)
    if call_binding is None:
        raise ValueError("native CSV group aggregate requires a supported grouped aggregate")
    call = call_binding.expr
    # Resolve the complete producer chain through canonical PipelineIR. This
    # permits `rows -> where -> group_count` without reimplementing AST-bucket
    # traversal in the native backend.
    from .execution_ir import build_execution_ir
    from .pipeline_ir import build_pipeline_ir
    pipeline = build_pipeline_ir(build_execution_ir(p.ast), call_binding.name)
    if "group" not in pipeline.kinds:
        raise ValueError("native CSV group aggregate requires a group pipeline stage")
    root_name = pipeline.source
    source_binding = next((b for b in p.ast.bindings if b.name == root_name), None)
    if source_binding is None or not (isinstance(source_binding.expr, Call) and source_binding.expr.name == "read_csv"):
        raise ValueError("native CSV group aggregate requires a read_csv root source")
    if len(source_binding.expr.args) != 1 or not isinstance(source_binding.expr.args[0], Literal) or not isinstance(source_binding.expr.args[0].value, str):
        raise ValueError("native CSV group aggregate requires a literal read_csv path")
    if not isinstance(p.show_exprs[0], Name) or p.show_exprs[0].name != call_binding.name:
        raise ValueError("native CSV group aggregate requires showing the grouped result directly")
    if call.name == "group_count":
        if len(call.args) != 2 or not isinstance(call.args[1], Literal) or not isinstance(call.args[1].value, str):
            raise ValueError("native group_count requires a literal group field")
    else:
        if len(call.args) != 3 or not all(isinstance(x, Literal) and isinstance(x.value, str) for x in call.args[1:]):
            raise ValueError(f"native {call.name} requires literal group and value fields")
    group_field = call.args[1].value
    value_field = call.args[2].value if call.name != "group_count" else None

    filter_stages = [stage for stage in pipeline.stages if stage.kind == "filter"]
    filters = [f for f in p.ast.filters if any(stage.result == f.result for stage in filter_stages)]
    if len(filters) > 1:
        raise ValueError("native CSV grouped aggregates support at most one direct text filter")
    if call.name != "group_count":
        map_stages = [stage for stage in pipeline.stages if stage.kind == "map"]
        if len(map_stages) != 1:
            raise ValueError(f"native {call.name} requires one explicit numeric record map")
        map_op = next((m for m in p.ast.maps if m.result == map_stages[0].result), None)
        if map_op is None or not isinstance(map_op.expr, Call) or not map_op.expr.args:
            raise ValueError(f"native {call.name} requires a record-constructor map")
        ctor = map_op.expr
        record = next((r for r in p.ast.records if r.name == ctor.name), None)
        if record is None:
            raise ValueError(f"native {call.name} requires a declared record constructor")
        field_exprs = dict(zip((f[0] for f in record.fields), ctor.args))
        key_expr = field_exprs.get(group_field)
        value_expr = field_exprs.get(value_field)
        if not (isinstance(key_expr, (Field, Property)) and isinstance(key_expr.base, Name) and key_expr.base.name in {"row", "item"}):
            raise ValueError(f"native {call.name} requires direct group-key field preservation")
        if not (isinstance(value_expr, Call) and value_expr.name == "to_number" and len(value_expr.args) == 1):
            raise ValueError(f"native {call.name} requires explicit to_number(value) in the mapped record")
        numeric_expr = value_expr.args[0]
        if not (isinstance(numeric_expr, (Field, Property)) and isinstance(numeric_expr.base, Name) and numeric_expr.base.name in {"row", "item"}):
            raise ValueError(f"native {call.name} requires direct to_number(row.field)")
        if numeric_expr.name != value_field or key_expr.name != group_field:
            raise ValueError(f"native {call.name} requires mapped fields to match aggregate fields")
    filter_field = None
    filter_value = None
    if filters:
        expr = filters[0].predicate.expr
        if not isinstance(expr, Compare) or expr.op != "==":
            raise ValueError("native CSV group_count filter requires field == text literal")
        if not (isinstance(expr.left, (Field, Property)) and isinstance(expr.left.base, Name) and expr.left.base.name in {"row", "item"}):
            raise ValueError("native CSV group_count filter requires a row/item field")
        if not isinstance(expr.right, Literal) or not isinstance(expr.right.value, str):
            raise ValueError("native CSV group_count filter requires a text literal")
        filter_field = expr.left.name
        filter_value = expr.right.value

    path_enc, path_len = _llvm_c_string(source_binding.expr.args[0].value)
    group_enc, group_len = _llvm_c_string(group_field)
    lines = [
        "; ModuleID = 'slang-native-csv-group-aggregate'", 'source_filename = "slang"',
        f'@csv_path = private constant [{path_len} x i8] c"{path_enc}"',
        f'@group_name = private constant [{group_len} x i8] c"{group_enc}"',
    ]
    if filter_field is not None:
        ff_enc, ff_len = _llvm_c_string(filter_field)
        fv_enc, fv_len = _llvm_c_string(filter_value)
        lines += [f'@filter_name = private constant [{ff_len} x i8] c"{ff_enc}"', f'@filter_value = private constant [{fv_len} x i8] c"{fv_enc}"']
    lines += [
        '', 'declare i64 @slang_csv_open(ptr)', 'declare i64 @slang_csv_field_index(i64, ptr)',
        'declare i32 @slang_csv_group_aggregate_print(i64, i64, i64, i32)',
        'declare i32 @slang_csv_group_count_where_text_print(i64, i64, i64, ptr)',
        'declare i32 @slang_csv_group_numeric_map_print(i64, i64, i64, i32)',
        'declare void @slang_csv_free(i64)', '', 'define i32 @main() {', 'entry:',
        f'  %csv = call i64 @slang_csv_open(ptr getelementptr inbounds ([{path_len} x i8], ptr @csv_path, i64 0, i64 0))',
        f'  %group_field = call i64 @slang_csv_field_index(i64 %csv, ptr getelementptr inbounds ([{group_len} x i8], ptr @group_name, i64 0, i64 0))',
    ]
    if filter_field is not None:
        lines += [
            f'  %filter_field = call i64 @slang_csv_field_index(i64 %csv, ptr getelementptr inbounds ([{ff_len} x i8], ptr @filter_name, i64 0, i64 0))',
            f'  %status = call i32 @slang_csv_group_count_where_text_print(i64 %csv, i64 %group_field, i64 %filter_field, ptr getelementptr inbounds ([{fv_len} x i8], ptr @filter_value, i64 0, i64 0))',
        ]
    else:
        if call.name == "group_count":
            lines += [
                '  %status = call i32 @slang_csv_group_aggregate_print(i64 %csv, i64 %group_field, i64 %group_field, i32 0)',
            ]
        else:
            value_enc, value_len = _llvm_c_string(value_field)
            lines[3:3] = [f'@value_name = private constant [{value_len} x i8] c"{value_enc}"']
            lines += [
                f'  %value_field = call i64 @slang_csv_field_index(i64 %csv, ptr getelementptr inbounds ([{value_len} x i8], ptr @value_name, i64 0, i64 0))',
                f'  %status = call i32 @slang_csv_group_numeric_map_print(i64 %csv, i64 %group_field, i64 %value_field, i32 {1 if call.name == "group_sum" else 2})',
            ]
    lines += ['  call void @slang_csv_free(i64 %csv)', '  ret i32 %status', '}', '']
    return '\n'.join(lines)

def native_csv_reduce_llvm_ir(p: Program):
    """Lower read_csv -> filter/map -> numeric reduce directly to native LLVM.

    CSV fields remain Text at the runtime boundary.  The lowering resolves
    field indices once, then scans rows in S-Lang order.  Only expressions
    whose types and semantics are explicit are accepted; unsupported forms
    continue to use the reference runtime rather than being approximated.
    """
    validate(p)
    if p.bodies or p.simulation or p.ast.sorts or p.ast.aggregates or p.ast.sequences:
        raise ValueError("native CSV reduce supports only read_csv filter/map/reduce pipelines")
    csv_bindings = {}
    for b in p.ast.bindings:
        if isinstance(b.expr, Call) and b.expr.name == "read_csv" and len(b.expr.args) == 1 and isinstance(b.expr.args[0], Literal) and isinstance(b.expr.args[0].value, str):
            csv_bindings[b.name] = b.expr.args[0].value
    if not csv_bindings or not p.ast.reduces:
        raise ValueError("native CSV reduce requires a literal read_csv binding and reduce")

    ops = list(p.ast.filters) + list(p.ast.maps)
    by_result = {op.result: op for op in ops}
    chains = []
    used_fields = set()

    def collect_fields(expr):
        if isinstance(expr, (Field, Property)) and isinstance(expr.base, Name) and expr.base.name in {"row", "item"}:
            used_fields.add(expr.name)
        elif isinstance(expr, (Binary, Compare, Logical)):
            collect_fields(expr.left)
            if getattr(expr, "right", None) is not None:
                collect_fields(expr.right)
        elif isinstance(expr, Conditional):
            collect_fields(expr.condition); collect_fields(expr.then_expr); collect_fields(expr.else_expr)
        elif isinstance(expr, Call):
            for arg in expr.args: collect_fields(arg)

    for red in p.ast.reduces:
        chain=[]; cur=red.source
        while cur in by_result:
            op=by_result[cur]; chain.append(op); cur=op.source
        chain.reverse()
        if cur not in csv_bindings:
            raise ValueError(f"native CSV reduce requires source '{cur}' to originate from read_csv")
        if not isinstance(red.initial, Literal) or not isinstance(red.initial.value, (int, float)) or isinstance(red.initial.value, bool):
            raise ValueError("native CSV reduce requires a numeric literal initial accumulator")
        if not isinstance(red.expr, Binary) or not isinstance(red.expr.left, Name) or red.expr.left.name != "acc" or red.expr.op not in {"+", "-", "*", "/", "^"}:
            raise ValueError("native CSV reduce supports only 'acc <+|-|*|/> current'")
        for op in chain:
            collect_fields(op.predicate.expr if isinstance(op, FilterOp) else op.expr)
        if isinstance(red.expr.right, (Field, Property)):
            collect_fields(red.expr.right)
        chains.append((red, chain, cur))

    if len({source for _, _, source in chains}) != 1:
        raise ValueError("native CSV reduce currently requires one shared read_csv source")
    source = chains[0][2]
    path = csv_bindings[source]
    path_encoded, path_len = _llvm_c_string(path)
    lines=["; ModuleID = 'slang-native-csv'", 'source_filename = "slang"', '']
    lines += [f'@csv_path = private constant [{path_len} x i8] c"{path_encoded}"', '@csv_fmt = private constant [7 x i8] c"%.15g\\0A\\00"', '']
    lines += [
        'declare i64 @slang_csv_open(ptr)',
        'declare i64 @slang_csv_count(i64)',
        'declare i64 @slang_csv_field_index(i64, ptr)',
        'declare ptr @slang_csv_get_text(i64, i64, i64)',
        'declare double @slang_to_number(ptr)',
        'declare void @slang_csv_free(i64)',
        'declare i32 @printf(ptr, ...)', 'declare i32 @strcmp(ptr, ptr)',
        '', 'define i32 @main() {', 'entry:',
        '  %%csv = call i64 @slang_csv_open(ptr getelementptr inbounds ([%d x i8], ptr @csv_path, i64 0, i64 0))' % path_len,
        '  %row_count = call i64 @slang_csv_count(i64 %csv)',
    ]

    # Resolve every referenced header exactly once.  Header names are S-Lang
    # source literals, so missing columns become a deterministic native error.
    field_ptrs={}
    field_indices={}
    for idx, field in enumerate(sorted(used_fields)):
        enc,n=_llvm_c_string(field)
        g=f'@csv_field_name_{idx}'
        lines.insert(3+idx, f'{g} = private constant [{n} x i8] c"{enc}"')
        v=f'%csv_field_{idx}'
        lines.append(f'  {v} = call i64 @slang_csv_field_index(i64 %csv, ptr getelementptr inbounds ([{n} x i8], ptr {g}, i64 0, i64 0))')
        field_ptrs[field]=g; field_indices[field]=v

    # The expression emitter returns an LLVM type and value.  CSV fields are
    # Text; map/reduce current values may become Number.
    def emit_expr(expr, row_value, current, serial):
        if isinstance(expr, Literal):
            if isinstance(expr.value, bool): return 'i1', '1' if expr.value else '0'
            if isinstance(expr.value, (int,float)) and not isinstance(expr.value,bool): return 'double', f'{float(expr.value):.17e}'
            if isinstance(expr.value, str):
                key=f'csv_lit_{serial}_{len(lines)}'; enc,n=_llvm_c_string(expr.value)
                lines.insert(4, f'@{key} = private constant [{n} x i8] c"{enc}"')
                return 'ptr', f'getelementptr inbounds ([{n} x i8], ptr @{key}, i64 0, i64 0)'
            raise ValueError('native CSV expressions support only scalar literals')
        if isinstance(expr, Name):
            if expr.name == 'item':
                if current is None: raise ValueError('native CSV item value is unavailable before a scalar map')
                return current
            raise ValueError(f"native CSV expression cannot resolve name '{expr.name}'")
        if isinstance(expr, (Field, Property)) and isinstance(expr.base, Name) and expr.base.name in {'row','item'}:
            if expr.name not in field_indices: raise ValueError(f"native CSV field '{expr.name}' was not indexed")
            v=f'%csv_text_{serial}_{len(lines)}'
            lines.append(f'  {v} = call ptr @slang_csv_get_text(i64 %csv, i64 {row_value}, i64 {field_indices[expr.name]})')
            return 'ptr', v
        if isinstance(expr, Call) and expr.name == 'to_number' and len(expr.args)==1:
            typ,val=emit_expr(expr.args[0],row_value,current,serial)
            if typ != 'ptr': raise ValueError('native CSV to_number requires Text')
            v=f'%csv_num_{serial}_{len(lines)}'; lines.append(f'  {v} = call double @slang_to_number(ptr {val})'); return 'double',v
        if isinstance(expr, Binary) and expr.op in {'+','-','*','/'}:
            lt,lv=emit_expr(expr.left,row_value,current,serial); rt,rv=emit_expr(expr.right,row_value,current,serial)
            if lt!='double' or rt!='double': raise ValueError('native CSV arithmetic requires Number operands')
            v=f'%csv_bin_{serial}_{len(lines)}'; op={'+':'fadd','-':'fsub','*':'fmul','/':'fdiv'}[expr.op]
            lines.append(f'  {v} = {op} double {lv}, {rv}'); return 'double',v
        if isinstance(expr, Compare) and expr.op in {'>','>=','<','<=','==','!='}:
            lt,lv=emit_expr(expr.left,row_value,current,serial); rt,rv=emit_expr(expr.right,row_value,current,serial)
            v=f'%csv_cmp_{serial}_{len(lines)}'
            if lt=='double' and rt=='double':
                pred={'>':'ogt','>=':'oge','<':'olt','<=':'ole','==':'oeq','!=':'one'}[expr.op]; lines.append(f'  {v} = fcmp {pred} double {lv}, {rv}')
            elif lt=='ptr' and rt=='ptr' and expr.op in {'==','!='}:
                lines.append(f'  %csv_strcmp_{serial}_{len(lines)} = call i32 @strcmp(ptr {lv}, ptr {rv})')
                cmpv=f'%csv_strcmpv_{serial}_{len(lines)}'; lines.append(f'  {cmpv} = call i32 @strcmp(ptr {lv}, ptr {rv})')
                lines.append(f'  {v} = icmp {"eq" if expr.op=="==" else "ne"} i32 {cmpv}, 0')
            else: raise ValueError('native CSV comparison requires matching Number operands or Text equality')
            return 'i1',v
        if isinstance(expr, Logical):
            if expr.op=='not':
                typ,val=emit_expr(expr.left,row_value,current,serial)
                if typ!='i1': raise ValueError('native CSV not requires Boolean')
                v=f'%csv_not_{serial}_{len(lines)}'; lines.append(f'  {v} = xor i1 {val}, true'); return 'i1',v
            lt,lv=emit_expr(expr.left,row_value,current,serial); rt,rv=emit_expr(expr.right,row_value,current,serial)
            if lt!='i1' or rt!='i1': raise ValueError('native CSV logical operators require Boolean operands')
            v=f'%csv_logic_{serial}_{len(lines)}'; lines.append(f'  {v} = {"and" if expr.op=="and" else "or"} i1 {lv}, {rv}'); return 'i1',v
        if isinstance(expr, Conditional):
            ct,cv=emit_expr(expr.condition,row_value,current,serial); tt,tv=emit_expr(expr.then_expr,row_value,current,serial); et,ev=emit_expr(expr.else_expr,row_value,current,serial)
            if ct!='i1' or tt!=et or tt not in {'double','i1'}: raise ValueError('native CSV conditional requires matching scalar branches')
            v=f'%csv_sel_{serial}_{len(lines)}'; lines.append(f'  {v} = select i1 {cv}, {tt} {tv}, {et} {ev}'); return tt,v
        raise ValueError(f'native CSV expression does not support {type(expr).__name__}')

    shown_names={x.name for x in p.show_exprs if isinstance(x,Name)}
    for ri,(red,chain,_) in enumerate(chains):
        loop=f'csv_reduce_loop_{ri}'; body=f'csv_reduce_body_{ri}'; done=f'csv_reduce_done_{ri}'; advance=f'csv_reduce_advance_{ri}'
        acc=f'%csv_acc_{ri}'
        lines += [f'  {acc} = alloca double', f'  store double {float(red.initial.value):.17e}, ptr {acc}', f'  br label %{loop}', f'{loop}:', f'  %row_i_{ri} = phi i64 [ 0, %entry ], [ %next_row_{ri}, %{advance} ]' if ri == 0 else f'  %row_i_{ri} = phi i64 [ 0, %csv_reduce_done_{ri-1} ], [ %next_row_{ri}, %{advance} ]', f'  %has_row_{ri} = icmp ult i64 %row_i_{ri}, %row_count', f'  br i1 %has_row_{ri}, label %{body}, label %{done}', f'{body}:']
        current=None
        serial=ri*1000
        for op in chain:
            serial += 1
            if isinstance(op, FilterOp):
                typ,val=emit_expr(op.predicate.expr,f'%row_i_{ri}',current,serial)
                if typ!='i1': raise ValueError('native CSV filter predicate must be Boolean')
                pass_label=f'csv_pass_{ri}_{serial}'
                lines += [f'  br i1 {val}, label %{pass_label}, label %{advance}', f'{pass_label}:']
            elif isinstance(op, MapOp):
                current=emit_expr(op.expr,f'%row_i_{ri}',current,serial)
                if current[0] != 'double': raise ValueError('native CSV reduce currently requires numeric map results')
        rhs=red.expr.right
        if isinstance(rhs, Name) and rhs.name=='item':
            if current is None: raise ValueError('native CSV reduce of item requires a scalar map')
            rhs_type,rhs_val=current
        else:
            rhs_type,rhs_val=emit_expr(rhs,f'%row_i_{ri}',current,serial+1)
        if rhs_type!='double': raise ValueError('native CSV reduce requires numeric current value')
        old=f'%csv_old_{ri}'; new=f'%csv_new_{ri}'; reduce_op={'+' : 'fadd', '-' : 'fsub', '*' : 'fmul', '/' : 'fdiv'}[red.expr.op]
        lines += [f'  {old} = load double, ptr {acc}', f'  {new} = {reduce_op} double {old}, {rhs_val}', f'  store double {new}, ptr {acc}', f'  br label %{advance}', f'{advance}:', f'  %next_row_{ri} = add i64 %row_i_{ri}, 1', f'  br label %{loop}', f'{done}:', f'  %final_{ri} = load double, ptr {acc}']
        if red.result in shown_names:
            lines.append(f'  call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([7 x i8], ptr @csv_fmt, i64 0, i64 0), double %final_{ri})')
    lines += ['  call void @slang_csv_free(i64 %csv)', '  ret i32 0', '}','']
    return '\n'.join(lines)


def native_csv_aggregate_llvm_ir(p: Program):
    """Lower a CSV pipeline ending in a native-safe scalar aggregate.

    Supported scalar aggregates are ``sum``, ``count``, ``min``, ``max`` and
    ``average``.  The lowering keeps the CSV traversal and expression subset
    identical to the native CSV reduce backend.  ``min``/``max`` use the first
    accepted row as their accumulator seed so negative and otherwise arbitrary
    numeric inputs retain normal S-Lang semantics; ``average`` keeps a separate
    count and sum.  Empty ``min``/``max``/``average`` collections are rejected
    at runtime, matching the reference aggregate contract.
    """
    validate(p)
    if len(p.ast.aggregates) != 1:
        raise ValueError("native CSV aggregate requires exactly one aggregate")
    agg = p.ast.aggregates[0]
    if agg.operation not in {"sum", "count", "min", "max", "average", "avg"}:
        raise ValueError("native CSV aggregate supports sum, count, min, max and average")
    if p.bodies or p.simulation or p.ast.reduces or p.ast.sequences:
        raise ValueError("native CSV aggregate supports only read_csv filter/map/sort/aggregate pipelines")

    csv_bindings = {}
    for b in p.ast.bindings:
        if (isinstance(b.expr, Call) and b.expr.name == "read_csv" and len(b.expr.args) == 1
                and isinstance(b.expr.args[0], Literal) and isinstance(b.expr.args[0].value, str)):
            csv_bindings[b.name] = b.expr.args[0].value
    if not csv_bindings:
        raise ValueError("native CSV aggregate requires a literal read_csv binding")

    # Consume the canonical pipeline IR produced by the semantic compiler.
    # The AST buckets remain the source of expression objects, but their order
    # is no longer re-derived independently by this backend.
    from .compiler_pipeline import compile_semantic_pipeline
    from .backend import native_capabilities
    planned = compile_semantic_pipeline(p.ast, native_capabilities().supported_strategies)
    pipeline = planned.pipeline_ir
    if pipeline is None or pipeline.terminal != agg.result:
        raise ValueError("native CSV aggregate requires a canonical pipeline IR")
    ops = {op.result: op for op in list(p.ast.filters) + list(p.ast.maps) + list(p.ast.sorts)}
    chain = [ops[stage.result] for stage in pipeline.stages if stage.result in ops]
    cur = pipeline.source
    if cur not in csv_bindings:
        raise ValueError(f"native CSV aggregate requires source '{cur}' to originate from read_csv")
    source = cur

    used_fields = set()
    def collect_fields(expr):
        if isinstance(expr, (Field, Property)) and isinstance(expr.base, Name) and expr.base.name in {"row", "item"}:
            used_fields.add(expr.name)
        elif isinstance(expr, (Binary, Compare, Logical)):
            collect_fields(expr.left)
            if getattr(expr, "right", None) is not None:
                collect_fields(expr.right)
        elif isinstance(expr, Conditional):
            collect_fields(expr.condition); collect_fields(expr.then_expr); collect_fields(expr.else_expr)
        elif isinstance(expr, Call):
            for arg in expr.args:
                collect_fields(arg)

    for op in chain:
        if isinstance(op, FilterOp):
            collect_fields(op.predicate.expr)
        elif isinstance(op, MapOp):
            collect_fields(op.expr)
        elif isinstance(op, SortOp):
            # Order is elided for order-independent scalar aggregates.
            pass
    collect_fields(agg.expr)

    path_encoded, path_len = _llvm_c_string(csv_bindings[source])
    lines = ["; ModuleID = 'slang-native-csv-aggregate'", 'source_filename = "slang"', '']
    lines += [f'@csv_path = private constant [{path_len} x i8] c"{path_encoded}"',
              '@csv_fmt = private constant [7 x i8] c"%.15g\\0A\\00"',
              '@csv_empty_msg = private constant [49 x i8] c"aggregate cannot operate on an empty collection\\0A\\00"', '']
    lines += [
        'declare i64 @slang_csv_open(ptr)',
        'declare i64 @slang_csv_count(i64)',
        'declare i64 @slang_csv_field_index(i64, ptr)',
        'declare ptr @slang_csv_get_text(i64, i64, i64)',
        'declare double @slang_to_number(ptr)',
        'declare void @slang_csv_free(i64)',
        'declare i32 @printf(ptr, ...)', 'declare i32 @strcmp(ptr, ptr)',
        '', 'define i32 @main() {', 'entry:',
        f'  %csv = call i64 @slang_csv_open(ptr getelementptr inbounds ([{path_len} x i8], ptr @csv_path, i64 0, i64 0))',
        '  %row_count = call i64 @slang_csv_count(i64 %csv)',
    ]

    field_ptrs = {}
    field_indices = {}
    for idx, field in enumerate(sorted(used_fields)):
        enc, n = _llvm_c_string(field)
        g = f'@csv_field_name_{idx}'
        lines.insert(3 + idx, f'{g} = private constant [{n} x i8] c"{enc}"')
        v = f'%csv_field_{idx}'
        lines.append(f'  {v} = call i64 @slang_csv_field_index(i64 %csv, ptr getelementptr inbounds ([{n} x i8], ptr {g}, i64 0, i64 0))')
        field_ptrs[field] = g; field_indices[field] = v

    def emit_expr(expr, row_value, current, serial):
        if isinstance(expr, Literal):
            if isinstance(expr.value, bool): return 'i1', '1' if expr.value else '0'
            if isinstance(expr.value, (int, float)) and not isinstance(expr.value, bool):
                return 'double', f'{float(expr.value):.17e}'
            if isinstance(expr.value, str):
                key = f'csv_lit_{serial}_{len(lines)}'; enc, n = _llvm_c_string(expr.value)
                lines.insert(4, f'@{key} = private constant [{n} x i8] c"{enc}"')
                return 'ptr', f'getelementptr inbounds ([{n} x i8], ptr @{key}, i64 0, i64 0)'
            raise ValueError('native CSV expressions support only scalar literals')
        if isinstance(expr, Name):
            if expr.name == 'item':
                if current is None: raise ValueError('native CSV item value is unavailable before a scalar map')
                return current
            raise ValueError(f"native CSV expression cannot resolve name '{expr.name}'")
        if isinstance(expr, (Field, Property)) and isinstance(expr.base, Name) and expr.base.name in {'row', 'item'}:
            if expr.name not in field_indices: raise ValueError(f"native CSV field '{expr.name}' was not indexed")
            v = f'%csv_text_{serial}_{len(lines)}'
            lines.append(f'  {v} = call ptr @slang_csv_get_text(i64 %csv, i64 {row_value}, i64 {field_indices[expr.name]})')
            return 'ptr', v
        if isinstance(expr, Call) and expr.name == 'to_number' and len(expr.args) == 1:
            typ, val = emit_expr(expr.args[0], row_value, current, serial)
            if typ != 'ptr': raise ValueError('native CSV to_number requires Text')
            v = f'%csv_num_{serial}_{len(lines)}'; lines.append(f'  {v} = call double @slang_to_number(ptr {val})'); return 'double', v
        if isinstance(expr, Binary) and expr.op in {'+', '-', '*', '/'}:
            lt, lv = emit_expr(expr.left, row_value, current, serial); rt, rv = emit_expr(expr.right, row_value, current, serial)
            if lt != 'double' or rt != 'double': raise ValueError('native CSV arithmetic requires Number operands')
            v = f'%csv_bin_{serial}_{len(lines)}'; lines.append(f'  {v} = { {"+":"fadd","-":"fsub","*":"fmul","/":"fdiv"}[expr.op] } double {lv}, {rv}'); return 'double', v
        if isinstance(expr, Compare) and expr.op in {'>', '>=', '<', '<=', '==', '!='}:
            lt, lv = emit_expr(expr.left, row_value, current, serial); rt, rv = emit_expr(expr.right, row_value, current, serial)
            v = f'%csv_cmp_{serial}_{len(lines)}'
            if lt == 'double' and rt == 'double':
                pred = {'>':'ogt','>=':'oge','<':'olt','<=':'ole','==':'oeq','!=':'one'}[expr.op]
                lines.append(f'  {v} = fcmp {pred} double {lv}, {rv}')
            elif lt == 'ptr' and rt == 'ptr' and expr.op in {'==', '!='}:
                cmpv = f'%csv_strcmpv_{serial}_{len(lines)}'; lines.append(f'  {cmpv} = call i32 @strcmp(ptr {lv}, ptr {rv})')
                lines.append(f'  {v} = icmp {"eq" if expr.op == "==" else "ne"} i32 {cmpv}, 0')
            else: raise ValueError('native CSV comparison requires matching Number operands or Text equality')
            return 'i1', v
        if isinstance(expr, Logical):
            if expr.op == 'not':
                typ, val = emit_expr(expr.left, row_value, current, serial)
                if typ != 'i1': raise ValueError('native CSV not requires Boolean')
                v = f'%csv_not_{serial}_{len(lines)}'; lines.append(f'  {v} = xor i1 {val}, true'); return 'i1', v
            lt, lv = emit_expr(expr.left, row_value, current, serial); rt, rv = emit_expr(expr.right, row_value, current, serial)
            if lt != 'i1' or rt != 'i1': raise ValueError('native CSV logical operators require Boolean operands')
            v = f'%csv_logic_{serial}_{len(lines)}'; lines.append(f'  {v} = {"and" if expr.op == "and" else "or"} i1 {lv}, {rv}'); return 'i1', v
        if isinstance(expr, Conditional):
            ct, cv = emit_expr(expr.condition, row_value, current, serial); tt, tv = emit_expr(expr.then_expr, row_value, current, serial); et, ev = emit_expr(expr.else_expr, row_value, current, serial)
            if ct != 'i1' or tt != et or tt not in {'double', 'i1'}: raise ValueError('native CSV conditional requires matching scalar branches')
            v = f'%csv_sel_{serial}_{len(lines)}'; lines.append(f'  {v} = select i1 {cv}, {tt} {tv}, {et} {ev}'); return tt, v
        raise ValueError(f'native CSV expression does not support {type(expr).__name__}')

    shown = isinstance(agg.result, str) and any(isinstance(x, Name) and x.name == agg.result for x in p.show_exprs)
    op = agg.operation
    needs_value = op != 'count'
    if op in {'sum', 'average', 'avg'}:
        lines += ['  %csv_sum = alloca double', '  store double 0.00000000000000000e+00, ptr %csv_sum']
    if op in {'average', 'avg'}:
        lines += ['  %csv_count = alloca i64', '  store i64 0, ptr %csv_count']
    if op in {'min', 'max'}:
        lines += ['  %csv_acc = alloca double', '  %csv_has = alloca i1', '  store i1 false, ptr %csv_has']
    if op == 'count':
        lines += ['  %csv_count = alloca i64', '  store i64 0, ptr %csv_count']

    loop, body, done, advance = 'csv_agg_loop', 'csv_agg_body', 'csv_agg_done', 'csv_agg_advance'
    lines += [f'  br label %{loop}', f'{loop}:', f'  %row_i = phi i64 [ 0, %entry ], [ %next_row, %{advance} ]',
              '  %has_row = icmp ult i64 %row_i, %row_count', f'  br i1 %has_row, label %{body}, label %{done}', f'{body}:']
    current = None
    serial = 100
    for stage in chain:
        serial += 1
        if isinstance(stage, FilterOp):
            typ, val = emit_expr(stage.predicate.expr, '%row_i', current, serial)
            if typ != 'i1': raise ValueError('native CSV filter predicate must be Boolean')
            passed = f'csv_agg_pass_{serial}'
            lines += [f'  br i1 {val}, label %{passed}, label %{advance}', f'{passed}:']
        elif isinstance(stage, MapOp):
            current = emit_expr(stage.expr, '%row_i', current, serial)
            if current[0] != 'double': raise ValueError('native CSV scalar aggregates currently require numeric map results')
        elif isinstance(stage, SortOp):
            # sum/count/min/max/average are order-independent.  Validate the
            # sort key shape, then elide the physical sort instead of paying
            # O(n log n) only to feed an order-independent terminal.
            expr = stage.spec.expr
            if isinstance(expr, Name) and expr.name == 'item':
                if current is None:
                    raise ValueError('native CSV sort requires a scalar map result for item')
            elif isinstance(expr, (Field, Property)) and isinstance(expr.base, Name) and expr.base.name in {'row', 'item'}:
                if expr.name not in field_indices and expr.base.name == 'row':
                    raise ValueError(f"native CSV sort field '{expr.name}' was not indexed")
            elif isinstance(expr, Literal) and isinstance(expr.value, (int, float, str)):
                pass
            else:
                raise ValueError('native CSV sort elimination supports direct row/item fields, item, or scalar literals')
    if needs_value:
        typ, value = emit_expr(agg.expr, '%row_i', current, serial + 1)
        if typ != 'double': raise ValueError('native CSV scalar aggregate requires a numeric expression')
    if op == 'count':
        old = '%csv_count_old'; new = '%csv_count_new'
        lines += [f'  {old} = load i64, ptr %csv_count', f'  {new} = add i64 {old}, 1', f'  store i64 {new}, ptr %csv_count', f'  br label %{advance}']
    elif op == 'sum':
        old, new = '%csv_sum_old', '%csv_sum_new'
        lines += [f'  {old} = load double, ptr %csv_sum', f'  {new} = fadd double {old}, {value}', f'  store double {new}, ptr %csv_sum', f'  br label %{advance}']
    elif op in {'average', 'avg'}:
        old, new = '%csv_sum_old', '%csv_sum_new'
        cold, cnew = '%csv_count_old', '%csv_count_new'
        lines += [f'  {old} = load double, ptr %csv_sum', f'  {new} = fadd double {old}, {value}', f'  store double {new}, ptr %csv_sum',
                  f'  {cold} = load i64, ptr %csv_count', f'  {cnew} = add i64 {cold}, 1', f'  store i64 {cnew}, ptr %csv_count', f'  br label %{advance}']
    else:
        old_has = '%csv_old_has'
        lines += [f'  {old_has} = load i1, ptr %csv_has', f'  br i1 {old_has}, label %csv_agg_update, label %csv_agg_seed',
                  'csv_agg_seed:', f'  store double {value}, ptr %csv_acc', '  store i1 true, ptr %csv_has', f'  br label %{advance}',
                  'csv_agg_update:', '  %csv_old_acc = load double, ptr %csv_acc']
        pred = 'olt' if op == 'min' else 'ogt'
        lines += [f'  %csv_better = fcmp {pred} double {value}, %csv_old_acc', f'  %csv_selected = select i1 %csv_better, double {value}, double %csv_old_acc', '  store double %csv_selected, ptr %csv_acc', f'  br label %{advance}']
    lines += [f'{advance}:', '  %next_row = add i64 %row_i, 1', f'  br label %{loop}', f'{done}:']

    if op == 'count':
        result_type, result_value = 'i64', '%csv_final_count'
        lines.append(f'  {result_value} = load i64, ptr %csv_count')
    elif op == 'sum':
        result_type, result_value = 'double', '%csv_final_sum'
        lines.append(f'  {result_value} = load double, ptr %csv_sum')
    elif op in {'average', 'avg'}:
        lines += ['  %csv_final_count = load i64, ptr %csv_count', '  %csv_nonempty = icmp ne i64 %csv_final_count, 0', '  br i1 %csv_nonempty, label %csv_agg_result, label %csv_agg_empty',
                  'csv_agg_empty:', '  call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([49 x i8], ptr @csv_empty_msg, i64 0, i64 0))', '  call void @slang_csv_free(i64 %csv)', '  ret i32 1', 'csv_agg_result:',
                  '  %csv_final_sum = load double, ptr %csv_sum', '  %csv_final_count_f = uitofp i64 %csv_final_count to double', '  %csv_final_avg = fdiv double %csv_final_sum, %csv_final_count_f']
        result_type, result_value = 'double', '%csv_final_avg'
    else:
        lines += ['  %csv_final_has = load i1, ptr %csv_has', '  br i1 %csv_final_has, label %csv_agg_result, label %csv_agg_empty',
                  'csv_agg_empty:', '  call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([49 x i8], ptr @csv_empty_msg, i64 0, i64 0))', '  call void @slang_csv_free(i64 %csv)', '  ret i32 1', 'csv_agg_result:',
                  '  %csv_final_acc = load double, ptr %csv_acc']
        result_type, result_value = 'double', '%csv_final_acc'
    if shown:
        if result_type == 'double':
            lines.append(f'  call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([7 x i8], ptr @csv_fmt, i64 0, i64 0), double {result_value})')
        else:
            lines.append(f'  %csv_count_double = uitofp i64 {result_value} to double')
            lines.append('  call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([7 x i8], ptr @csv_fmt, i64 0, i64 0), double %csv_count_double)')
    lines += ['  call void @slang_csv_free(i64 %csv)', '  ret i32 0', '}','']
    return '\n'.join(lines)

def native_csv_multi_aggregate_llvm_ir(p: Program):
    """Lower multiple scalar aggregates sharing one CSV pipeline in one scan."""
    validate(p)
    aggs = list(p.ast.aggregates)
    if len(aggs) < 2:
        raise ValueError("native CSV multi-aggregate backend requires at least two aggregates")
    allowed = {"sum", "count", "min", "max", "average", "avg"}
    if any(a.operation not in allowed for a in aggs):
        raise ValueError("native CSV multi-aggregate supports sum, count, min, max and average")
    if p.bodies or p.simulation or p.ast.sorts or p.ast.reduces or p.ast.sequences:
        raise ValueError("native CSV multi-aggregate supports only read_csv filter/map/aggregate pipelines")

    csv_bindings = {}
    for b in p.ast.bindings:
        if (isinstance(b.expr, Call) and b.expr.name == "read_csv" and len(b.expr.args) == 1
                and isinstance(b.expr.args[0], Literal) and isinstance(b.expr.args[0].value, str)):
            csv_bindings[b.name] = b.expr.args[0].value
    if not csv_bindings:
        raise ValueError("native CSV multi-aggregate requires a literal read_csv binding")

    # All terminal aggregates must consume the same pipeline. This guarantees
    # that one native scan has exactly the same filter/map semantics for every
    # result.
    sources = {a.source for a in aggs}
    if len(sources) != 1:
        raise ValueError("native CSV multi-aggregate requires a shared terminal source")
    terminal_source = aggs[0].source
    from .compiler_pipeline import compile_semantic_pipeline
    from .backend import native_capabilities
    planned = compile_semantic_pipeline(p.ast, native_capabilities().supported_strategies)
    pipeline = planned.pipeline_ir
    aggregate_terminal = aggs[0].result
    if pipeline is None or pipeline.terminal != aggregate_terminal:
        raise ValueError("native CSV multi-aggregate requires a canonical pipeline IR")
    ops = {op.result: op for op in list(p.ast.filters) + list(p.ast.maps) + list(p.ast.sorts)}
    chain = [ops[stage.result] for stage in pipeline.stages if stage.result in ops]
    cur = pipeline.source
    if terminal_source not in {stage.result for stage in pipeline.stages}:
        raise ValueError("native CSV multi-aggregate requires all terminals to share the canonical source chain")
    if cur not in csv_bindings:
        raise ValueError(f"native CSV multi-aggregate requires source '{cur}' to originate from read_csv")
    source = cur

    used_fields = set()
    def collect_fields(expr):
        if isinstance(expr, (Field, Property)) and isinstance(expr.base, Name) and expr.base.name in {"row", "item"}:
            used_fields.add(expr.name)
        elif isinstance(expr, (Binary, Compare, Logical)):
            collect_fields(expr.left)
            if getattr(expr, "right", None) is not None:
                collect_fields(expr.right)
        elif isinstance(expr, Conditional):
            collect_fields(expr.condition); collect_fields(expr.then_expr); collect_fields(expr.else_expr)
        elif isinstance(expr, Call):
            for arg in expr.args: collect_fields(arg)
    for stage in chain:
        if isinstance(stage, FilterOp):
            collect_fields(stage.predicate.expr)
        elif isinstance(stage, MapOp):
            collect_fields(stage.expr)
        elif isinstance(stage, SortOp):
            # The sort is order-elided for order-independent aggregates; its
            # key is validated separately in the execution loop.
            pass
    for agg in aggs:
        collect_fields(agg.expr)

    path_encoded, path_len = _llvm_c_string(csv_bindings[source])
    lines = ["; ModuleID = 'slang-native-csv-multi-aggregate'", 'source_filename = "slang"', '']
    lines += [f'@csv_path = private constant [{path_len} x i8] c"{path_encoded}"',
              '@csv_fmt = private constant [7 x i8] c"%.15g\\0A\\00"',
              '@csv_empty_msg = private constant [49 x i8] c"aggregate cannot operate on an empty collection\\0A\\00"', '']
    lines += [
        'declare i64 @slang_csv_open(ptr)', 'declare i64 @slang_csv_count(i64)',
        'declare i64 @slang_csv_field_index(i64, ptr)', 'declare ptr @slang_csv_get_text(i64, i64, i64)',
        'declare double @slang_to_number(ptr)', 'declare void @slang_csv_free(i64)',
        'declare i32 @printf(ptr, ...)', 'declare i32 @strcmp(ptr, ptr)', '',
        'define i32 @main() {', 'entry:',
        f'  %csv = call i64 @slang_csv_open(ptr getelementptr inbounds ([{path_len} x i8], ptr @csv_path, i64 0, i64 0))',
        '  %row_count = call i64 @slang_csv_count(i64 %csv)',
    ]
    field_indices = {}
    for idx, field in enumerate(sorted(used_fields)):
        enc, n = _llvm_c_string(field)
        g=f'@csv_multi_field_name_{idx}'
        lines.insert(3 + idx, f'{g} = private constant [{n} x i8] c"{enc}"')
        v=f'%csv_multi_field_{idx}'
        lines.append(f'  {v} = call i64 @slang_csv_field_index(i64 %csv, ptr getelementptr inbounds ([{n} x i8], ptr {g}, i64 0, i64 0))')
        field_indices[field]=v

    def emit_expr(expr, row_value, current, serial):
        if isinstance(expr, Literal):
            if isinstance(expr.value, bool): return 'i1', '1' if expr.value else '0'
            if isinstance(expr.value, (int,float)) and not isinstance(expr.value,bool): return 'double', f'{float(expr.value):.17e}'
            if isinstance(expr.value,str):
                key=f'csv_multi_lit_{serial}_{len(lines)}'; enc,n=_llvm_c_string(expr.value)
                lines.insert(4, f'@{key} = private constant [{n} x i8] c"{enc}"')
                return 'ptr', f'getelementptr inbounds ([{n} x i8], ptr @{key}, i64 0, i64 0)'
            raise ValueError('native CSV expressions support only scalar literals')
        if isinstance(expr, Name):
            if expr.name == 'item':
                if current is None: raise ValueError('native CSV item value is unavailable before a scalar map')
                return current
            raise ValueError(f"native CSV expression cannot resolve name '{expr.name}'")
        if isinstance(expr,(Field,Property)) and isinstance(expr.base,Name) and expr.base.name in {'row','item'}:
            if expr.name not in field_indices: raise ValueError(f"native CSV field '{expr.name}' was not indexed")
            v=f'%csv_multi_text_{serial}_{len(lines)}'
            lines.append(f'  {v} = call ptr @slang_csv_get_text(i64 %csv, i64 {row_value}, i64 {field_indices[expr.name]})')
            return 'ptr',v
        if isinstance(expr,Call) and expr.name=='to_number' and len(expr.args)==1:
            typ,val=emit_expr(expr.args[0],row_value,current,serial)
            if typ!='ptr': raise ValueError('native CSV to_number requires Text')
            v=f'%csv_multi_num_{serial}_{len(lines)}'; lines.append(f'  {v} = call double @slang_to_number(ptr {val})'); return 'double',v
        if isinstance(expr,Binary) and expr.op in {'+','-','*','/'}:
            lt,lv=emit_expr(expr.left,row_value,current,serial); rt,rv=emit_expr(expr.right,row_value,current,serial)
            if lt!='double' or rt!='double': raise ValueError('native CSV arithmetic requires Number operands')
            v=f'%csv_multi_bin_{serial}_{len(lines)}'; lines.append(f'  {v} = { {"+":"fadd","-":"fsub","*":"fmul","/":"fdiv"}[expr.op] } double {lv}, {rv}'); return 'double',v
        if isinstance(expr,Compare) and expr.op in {'>','>=','<','<=','==','!='}:
            lt,lv=emit_expr(expr.left,row_value,current,serial); rt,rv=emit_expr(expr.right,row_value,current,serial)
            v=f'%csv_multi_cmp_{serial}_{len(lines)}'
            if lt=='double' and rt=='double':
                pred={'>':'ogt','>=':'oge','<':'olt','<=':'ole','==':'oeq','!=':'one'}[expr.op]
                lines.append(f'  {v} = fcmp {pred} double {lv}, {rv}')
            elif lt=='ptr' and rt=='ptr' and expr.op in {'==','!='}:
                cmpv=f'%csv_multi_strcmp_{serial}_{len(lines)}'; lines.append(f'  {cmpv} = call i32 @strcmp(ptr {lv}, ptr {rv})')
                lines.append(f'  {v} = icmp {"eq" if expr.op=="==" else "ne"} i32 {cmpv}, 0')
            else: raise ValueError('native CSV comparison requires matching Number operands or Text equality')
            return 'i1',v
        if isinstance(expr,Logical):
            if expr.op=='not':
                typ,val=emit_expr(expr.left,row_value,current,serial)
                if typ!='i1': raise ValueError('native CSV not requires Boolean')
                v=f'%csv_multi_not_{serial}_{len(lines)}'; lines.append(f'  {v} = xor i1 {val}, true'); return 'i1',v
            lt,lv=emit_expr(expr.left,row_value,current,serial); rt,rv=emit_expr(expr.right,row_value,current,serial)
            if lt!='i1' or rt!='i1': raise ValueError('native CSV logical operators require Boolean operands')
            v=f'%csv_multi_logic_{serial}_{len(lines)}'; lines.append(f'  {v} = {"and" if expr.op=="and" else "or"} i1 {lv}, {rv}'); return 'i1',v
        if isinstance(expr,Conditional):
            ct,cv=emit_expr(expr.condition,row_value,current,serial); tt,tv=emit_expr(expr.then_expr,row_value,current,serial); et,ev=emit_expr(expr.else_expr,row_value,current,serial)
            if ct!='i1' or tt!=et or tt not in {'double','i1'}: raise ValueError('native CSV conditional requires matching scalar branches')
            v=f'%csv_multi_sel_{serial}_{len(lines)}'; lines.append(f'  {v} = select i1 {cv}, {tt} {tv}, {et} {ev}'); return tt,v
        raise ValueError(f'native CSV expression does not support {type(expr).__name__}')

    # Accumulator storage is allocated once. Every accepted row updates every
    # requested aggregate before advancing the single CSV cursor.
    for idx, agg in enumerate(aggs):
        if agg.operation in {'sum','average','avg'}:
            lines += [f'  %ma_sum_{idx} = alloca double', f'  store double 0.00000000000000000e+00, ptr %ma_sum_{idx}']
        if agg.operation in {'average','avg','count'}:
            lines += [f'  %ma_count_{idx} = alloca i64', f'  store i64 0, ptr %ma_count_{idx}']
        if agg.operation in {'min','max'}:
            lines += [f'  %ma_acc_{idx} = alloca double', f'  %ma_has_{idx} = alloca i1', f'  store i1 false, ptr %ma_has_{idx}']

    lines += ['  br label %ma_loop', 'ma_loop:', '  %ma_row = phi i64 [ 0, %entry ], [ %ma_next, %ma_advance ]',
              '  %ma_has_row = icmp ult i64 %ma_row, %row_count',
              '  br i1 %ma_has_row, label %ma_body, label %ma_done', 'ma_body:']
    current=None; serial=200
    for stage in chain:
        serial += 1
        if isinstance(stage,FilterOp):
            typ,val=emit_expr(stage.predicate.expr,'%ma_row',current,serial)
            if typ!='i1': raise ValueError('native CSV filter predicate must be Boolean')
            passed=f'ma_pass_{serial}'
            lines += [f'  br i1 {val}, label %{passed}, label %ma_advance', f'{passed}:']
        elif isinstance(stage,MapOp):
            current=emit_expr(stage.expr,'%ma_row',current,serial)
            if current[0]!='double': raise ValueError('native CSV multi-aggregate requires numeric map results')

    any_nonempty = any(a.operation in {'min','max','average','avg'} for a in aggs)
    for idx, agg in enumerate(aggs):
        last = idx == len(aggs) - 1
        if agg.operation == 'count':
            lines += [f'  %ma_count_old_{idx} = load i64, ptr %ma_count_{idx}', f'  %ma_count_new_{idx} = add i64 %ma_count_old_{idx}, 1', f'  store i64 %ma_count_new_{idx}, ptr %ma_count_{idx}']
            if last:
                lines.append('  br label %ma_advance')
            continue
        typ,value=emit_expr(agg.expr,'%ma_row',current,serial+idx+1)
        if typ!='double': raise ValueError('native CSV multi-aggregate requires numeric aggregate expressions')
        if agg.operation=='sum':
            lines += [f'  %ma_old_{idx} = load double, ptr %ma_sum_{idx}', f'  %ma_new_{idx} = fadd double %ma_old_{idx}, {value}', f'  store double %ma_new_{idx}, ptr %ma_sum_{idx}']
        elif agg.operation in {'average','avg'}:
            lines += [f'  %ma_old_{idx} = load double, ptr %ma_sum_{idx}', f'  %ma_new_{idx} = fadd double %ma_old_{idx}, {value}', f'  store double %ma_new_{idx}, ptr %ma_sum_{idx}', f'  %ma_count_old_{idx} = load i64, ptr %ma_count_{idx}', f'  %ma_count_new_{idx} = add i64 %ma_count_old_{idx}, 1', f'  store i64 %ma_count_new_{idx}, ptr %ma_count_{idx}']
        else:
            lines += [f'  %ma_old_has_{idx} = load i1, ptr %ma_has_{idx}', f'  br i1 %ma_old_has_{idx}, label %ma_update_{idx}, label %ma_seed_{idx}', f'ma_seed_{idx}:', f'  store double {value}, ptr %ma_acc_{idx}', f'  store i1 true, ptr %ma_has_{idx}', f'  br label %ma_after_acc_{idx}', f'ma_update_{idx}:', f'  %ma_old_acc_{idx} = load double, ptr %ma_acc_{idx}']
            pred='olt' if agg.operation=='min' else 'ogt'
            lines += [f'  %ma_better_{idx} = fcmp {pred} double {value}, %ma_old_acc_{idx}', f'  %ma_selected_{idx} = select i1 %ma_better_{idx}, double {value}, double %ma_old_acc_{idx}', f'  store double %ma_selected_{idx}, ptr %ma_acc_{idx}', f'  br label %ma_after_acc_{idx}', f'ma_after_acc_{idx}:']
        if last:
            lines.append('  br label %ma_advance')
    lines += ['ma_advance:', '  %ma_next = add i64 %ma_row, 1', '  br label %ma_loop', 'ma_done:']

    if any_nonempty:
        lines += ['  %ma_nonempty = icmp ne i64 %row_count, 0', '  br i1 %ma_nonempty, label %ma_results, label %ma_empty',
                  'ma_empty:', '  call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([49 x i8], ptr @csv_empty_msg, i64 0, i64 0))', '  call void @slang_csv_free(i64 %csv)', '  ret i32 1', 'ma_results:']
    shown = {x.name for x in p.show_exprs if isinstance(x,Name)}
    for idx, agg in enumerate(aggs):
        if agg.result not in shown: continue
        if agg.operation=='count':
            lines += [f'  %ma_print_count_{idx} = load i64, ptr %ma_count_{idx}', f'  %ma_print_count_f_{idx} = uitofp i64 %ma_print_count_{idx} to double', f'  call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([7 x i8], ptr @csv_fmt, i64 0, i64 0), double %ma_print_count_f_{idx})']
        elif agg.operation in {'sum'}:
            lines += [f'  %ma_print_{idx} = load double, ptr %ma_sum_{idx}', f'  call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([7 x i8], ptr @csv_fmt, i64 0, i64 0), double %ma_print_{idx})']
        elif agg.operation in {'average','avg'}:
            lines += [f'  %ma_print_sum_{idx} = load double, ptr %ma_sum_{idx}', f'  %ma_print_count_{idx} = load i64, ptr %ma_count_{idx}', f'  %ma_print_count_f_{idx} = uitofp i64 %ma_print_count_{idx} to double', f'  %ma_print_avg_{idx} = fdiv double %ma_print_sum_{idx}, %ma_print_count_f_{idx}', f'  call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([7 x i8], ptr @csv_fmt, i64 0, i64 0), double %ma_print_avg_{idx})']
        else:
            lines += [f'  %ma_print_acc_{idx} = load double, ptr %ma_acc_{idx}', f'  call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([7 x i8], ptr @csv_fmt, i64 0, i64 0), double %ma_print_acc_{idx})']
    lines += ['  call void @slang_csv_free(i64 %csv)', '  ret i32 0', '}','']
    return '\n'.join(lines)

def llvm_ir(p:Program, type_contract=None, schema_contract=None):
    """Lower supported S-Lang programs using the resolved semantic contract.

    ``type_contract`` is supplied by the compiler pipeline. When present,
    backend lowering does not rerun semantic type validation; the ExecutionIR
    contract is authoritative. Direct callers retain the legacy validation
    behavior by omitting it.
    """
    if any(isinstance(statement, IfOp) for statement in getattr(p.ast, "top_level_statements", [])):
        raise ValueError("native LLVM lowering does not yet support top-level block if; use 'slang run' for interpreter execution")
    if type_contract is None:
        validate(p)
    # Structured schemas are supplied by semantic analysis. They are not
    # re-derived here; native lowering may use them as an authoritative field
    # contract when lowering record collections.
    if schema_contract is not None:
        setattr(p, "_backend_schema_contract", tuple(schema_contract))
    # Built-in geometry and user entities have compact native scalar backends.
    if p.circles and not p.ast.entities and not p.ast.records:
        return _native_circle_llvm_ir(p)
    if p.ast.entities and not p.ast.records:
        return _native_entity_llvm_ir(p)
    # External CSV grouped aggregates have a dedicated runtime ABI. Select
    # this before the generic record-collection backend because an explicit
    # numeric record map is itself part of the CSV pipeline.
    grouped_calls = [b for b in p.ast.bindings if isinstance(b.expr, Call) and b.expr.name in {"group_count", "group_sum", "group_average", "group_min", "group_max"}]
    if len(grouped_calls) >= 2 and any(isinstance(b.expr, Call) and b.expr.name == "read_csv" for b in p.ast.bindings):
        return "; selected-strategy = native-csv-group-multi-aggregate\n" + native_csv_group_multi_aggregate_llvm_ir(p)
    if grouped_calls and any(isinstance(b.expr, Call) and b.expr.name == "read_csv" for b in p.ast.bindings):
        return "; selected-strategy = native-csv-group-aggregate\n" + native_csv_group_aggregate_llvm_ir(p)
    # List<Record<T>> has a dedicated native collection lowering before the
    # scalar named-record backend.
    if p.ast.records and p.ast.functions and (p.ast.filters or p.ast.maps):
        return record_collection_llvm_ir(p, schema_contract=schema_contract)
    if p.ast.records and not p.ast.functions:
        if p.ast.sorts and (p.ast.aggregates or p.ast.reduces):
            # Keep structured records through sorting unless a scalar map
            # projects the record before the sort. That projection changes
            # the collection element type; the scalar-boundary lowering in
            # record_collection_llvm_ir must then own the sort/reduce path.
            record_sources = set()
            for binding in p.ast.bindings:
                value = binding.expr
                if isinstance(value, Literal) and isinstance(value.value, list) and value.value:
                    rows = value.value
                    if all(isinstance(item, Call) and any(item.name == record.name for record in p.ast.records) for item in rows):
                        record_sources.add(binding.name)
            by_result = {op.result: op for op in list(p.ast.filters) + list(p.ast.maps)}
            cursor = p.ast.sorts[0].source
            scalar_projection_before_sort = False
            visited = set()
            while cursor not in record_sources and cursor in by_result and cursor not in visited:
                visited.add(cursor)
                operation = by_result[cursor]
                if isinstance(operation, MapOp):
                    is_record_map = isinstance(operation.expr, Call) and any(
                        operation.expr.name == record.name for record in p.ast.records
                    )
                    if not is_record_map:
                        scalar_projection_before_sort = True
                        break
                cursor = operation.source
            if scalar_projection_before_sort:
                return record_collection_llvm_ir(p, schema_contract=schema_contract)
            return record_collection_sort_llvm_ir(p)
        if p.ast.aggregates or p.ast.reduces:
            return record_collection_llvm_ir(p, schema_contract=schema_contract)
        if p.ast.sorts:
            # Use the structured-record sort backend only while the pipeline
            # still carries records. A map before sort may intentionally
            # project a numeric scalar collection and must retain the older
            # numeric sort/reduce/aggregate backend.
            record_sources=set()
            for b in p.ast.bindings:
                if isinstance(b.expr, Literal) and isinstance(b.expr.value, list) and b.expr.value:
                    xs=b.expr.value
                    if all(isinstance(x, Call) and any(x.name==r.name for r in p.ast.records) for x in xs):
                        record_sources.add(b.name)
            by_result={op.result: op for op in p.ast.filters + p.ast.maps}
            cursor=p.ast.sorts[0].source
            carries_records=True
            while cursor not in record_sources:
                op=by_result.get(cursor)
                if op is None:
                    carries_records=False; break
                if isinstance(op, MapOp):
                    carries_records=False; break
                cursor=op.source
            if carries_records:
                return record_collection_sort_llvm_ir(p)
        if p.ast.filters or p.ast.maps:
            return record_collection_llvm_ir(p, schema_contract=schema_contract)
        return record_llvm_ir(p)
    # Explicitly typed user functions use the native scalar control-flow backend.
    if p.ast.functions:
        return native_program_llvm_ir(p, schema_contract=schema_contract)
    # Native CSV sources use the same deterministic filter/map/reduce/aggregate
    # semantics as ordinary collections, but read the external file through the
    # shared C runtime instead of materializing rows in the Python interpreter.
    if any(isinstance(b.expr, Call) and b.expr.name == "read_csv" for b in p.ast.bindings):
        if p.ast.sorts and not p.ast.reduces and not p.ast.aggregates:
            return "; selected-strategy = native-csv-sort\n" + native_csv_sort_llvm_ir(p)
        if p.ast.reduces:
            selected_csv = _selected_native_strategy(p)
            if selected_csv not in {"fused-filter-map-reduce", "sequential-reduce"}:
                raise ValueError(f"selected strategy '{selected_csv}' cannot be lowered by the native CSV reduce backend")
            return f"; selected-strategy = {selected_csv}\n" + native_csv_reduce_llvm_ir(p)
        if p.ast.aggregates:
            selected_csv = _selected_native_strategy(p)
            if selected_csv not in {"sequential-aggregate", "fused-filter-map-aggregate"}:
                raise ValueError(f"selected strategy '{selected_csv}' cannot be lowered by the native CSV aggregate backend")
            if len(p.ast.aggregates) > 1:
                return f"; selected-strategy = {selected_csv}\n; multi-aggregate = single-pass\n" + native_csv_multi_aggregate_llvm_ir(p)
            return f"; selected-strategy = {selected_csv}\n" + native_csv_aggregate_llvm_ir(p)
    # Scalar filesystem/system bindings have a concrete native ABI. Keep this
    # path separate from collection lowering so the native subset can grow
    # without pretending that arbitrary text/list values are LLVM-lowerable.
    if p.ast.bindings and not (p.ast.filters or p.ast.maps or p.ast.sorts or p.ast.aggregates or p.ast.reduces or p.ast.sequences or p.ast.goals or p.ast.path_goals or p.ast.satisfy_goals or p.bodies or p.simulation):
        system_calls = {"exists", "file_size", "is_file", "is_directory", "write", "read", "read_lines", "list_directory", "list_files", "list_directories", "make_directory", "make_directories", "remove_directory", "remove_directory_tree", "remove_file", "copy_file", "move_file", "write_lines", "basename", "dirname", "extension", "join_path", "normalize_path", "arguments", "environment", "run_process", "run_program", "run_program_with_environment", "current_directory", "platform_name", "process_id", "sleep_seconds", "home_directory", "temp_directory", "executable_path", "command_exists", "trim", "lower", "upper", "starts_with", "ends_with", "replace", "split"}
        if all(_native_system_calls_in_expr(b.expr) <= system_calls for b in p.ast.bindings):
            return "; selected-strategy = generic\n" + system_llvm_ir(p)
    # Backend capability is checked after semantic strategy selection.  This
    # prevents the native emitter from silently substituting an implementation
    # for a strategy selected by the compiler.
    from .compiler_pipeline import compile_semantic_pipeline
    from .backend import native_capabilities, validate_backend_capabilities
    validate_backend_capabilities(compile_semantic_pipeline(p.ast, native_capabilities().supported_strategies), native_capabilities())
    selected = _selected_native_strategy(p)
    if p.ast.sequences:
        if selected not in {"sequence-engine", "sequential-reduce", "generic"}:
            raise ValueError(f"selected strategy '{selected}' cannot be lowered by the native sequence backend")
        return "; selected-strategy = sequence-engine\n" + sequence_llvm_ir(p)
    if p.ast.reduces:
        if p.ast.sorts:
            if selected != "sequential-reduce":
                raise ValueError(f"selected strategy '{selected}' cannot be lowered by the native sort-reduce backend")
            if p.ast.filters or p.ast.maps:
                return "; selected-strategy = sequential-reduce\n" + pipeline_sort_reduce_llvm_ir(p)
            return "; selected-strategy = sequential-reduce\n" + sort_reduce_llvm_ir(p)
        if (p.ast.filters or p.ast.maps) and selected != "fused-filter-map-reduce":
            raise ValueError(f"selected strategy '{selected}' cannot be lowered by the native reduce backend for this pipeline")
        if selected == "fused-filter-map-reduce":
            return "; selected-strategy = fused-filter-map-reduce\n" + fused_reduce_llvm_ir(p)
        if selected.startswith("fused-"):
            raise ValueError(f"native backend does not yet implement selected strategy '{selected}'")
        return "; selected-strategy = " + selected + "\n" + reduce_llvm_ir(p)
    if p.ast.aggregates:
        if len(p.ast.aggregates) > 1 and not any(isinstance(b.expr, Call) and b.expr.name == "read_csv" for b in p.ast.bindings):
            aggregate_sources = {item.source for item in p.ast.aggregates}
            if aggregate_sources <= set(p.data_tables or {}):
                # The scalar backend remains the compact path when every
                # terminal consumes the same field. For heterogeneous fields,
                # use the row-aware fused backend so each accumulator reads
                # its own column during the same source traversal.
                aggregate_fields = set()
                for terminal in p.ast.aggregates:
                    expr = terminal.expr
                    if expr is None:
                        continue
                    stack = [expr]
                    while stack:
                        node = stack.pop()
                        if isinstance(node, (Field, Property)) and isinstance(node.base, Name) and node.base.name == "row":
                            aggregate_fields.add(node.name)
                        elif isinstance(node, (Binary, Compare, Logical)):
                            stack.append(node.left)
                            if getattr(node, "right", None) is not None:
                                stack.append(node.right)
                        elif isinstance(node, Conditional):
                            stack.extend((node.condition, node.then_expr, node.else_expr))
                        elif isinstance(node, Call):
                            stack.extend(node.args)
                if len(aggregate_fields) <= 1:
                    return "; selected-strategy = native-multi-aggregate\n; multi-aggregate = shared-single-pass\n" + aggregate_llvm_ir(p)
            return "; selected-strategy = native-multi-aggregate\n; multi-aggregate = shared-single-pass\n" + fused_aggregate_llvm_ir(p)
        if p.ast.bindings and any(isinstance(b.expr, Call) and b.expr.name == "read_csv" for b in p.ast.bindings):
            if p.ast.aggregates[0].operation in {"sum", "count"} and len(p.ast.aggregates) == 1:
                return "; selected-strategy = native-csv-aggregate\n" + native_csv_aggregate_llvm_ir(p)
        if (len(p.ast.filters) == 1 and len(p.ast.sorts) == 1 and len(p.ast.maps) == 1 and len(p.ast.aggregates) == 1 and not p.ast.reduces):
            try:
                return "; selected-strategy = record-preserving-filter-sort-map-aggregate\n" + _record_preserving_pipeline_aggregate_llvm_ir(p)
            except ValueError:
                pass
        if selected == "fused-filter-map-aggregate":
            return "; selected-strategy = fused-filter-map-aggregate\n" + fused_aggregate_llvm_ir(p)
        if selected.startswith("fused-"):
            raise ValueError(f"native backend does not yet implement selected strategy '{selected}'")
        return "; selected-strategy = " + selected + "\n" + aggregate_llvm_ir(p)
    if p.ast.sorts:
        if selected.startswith("fused-"):
            raise ValueError(f"native backend does not yet implement selected strategy '{selected}'")
        return "; selected-strategy = " + selected + "\n" + sort_llvm_ir(p, schema_contract=schema_contract)
    if p.ast.filters or p.ast.maps:
        return "; selected-strategy = " + selected + "\n" + collection_llvm_ir(p)
    # Simple scalar `show` programs are a valid native-JIT target too.  Keep
    # this branch ahead of the gravity-simulation fallback: otherwise a plain
    # arithmetic program reaches `p.simulation` even when it is None.
    if p.show_exprs and not (p.ast.bindings or p.ast.filters or p.ast.maps or p.ast.sorts or p.ast.aggregates or p.ast.reduces or p.ast.sequences or p.ast.functions or p.ast.goals or p.ast.path_goals or p.ast.satisfy_goals or p.bodies or p.simulation):
        lines = ['; selected-strategy = scalar-show', 'declare i32 @printf(ptr, ...)', 'declare double @llvm.pow.f64(double, double)', '@slang_scalar_fmt = private constant [7 x i8] c"%.17g\\0A\\00"', '', 'define i32 @main() {', 'entry:']
        for i, expr in enumerate(p.show_exprs):
            value = _llvm_scalar_expr(expr, None, lines, i)
            lines.append(f'  %show_ptr_{i} = getelementptr [7 x i8], ptr @slang_scalar_fmt, i64 0, i64 0')
            lines.append(f'  call i32 (ptr, ...) @printf(ptr %show_ptr_{i}, double {value})')
        lines.extend(['  ret i32 0', '}', ''])
        return '\n'.join(lines)
    if p.simulation is None:
        raise ValueError("native LLVM backend does not support this program shape; use 'slang run' without --native-jit")
    t,a,duration,step=p.simulation
    by={b.name:b for b in p.bodies}
    tb,ab=by[t],by[a]
    x=tb.fields["position"].value
    v=tb.fields["velocity"].value
    m=ab.fields["mass"].value
    G=6.67430e-11
    steps=int(math.floor(duration/step + 1e-12))
    remainder=duration-steps*step
    def c(v): return f"0x{struct.unpack('Q', struct.pack('d', float(v)))[0]:016X}"
    fmt_pos="%s.position = %.15g m\\0A\\00"; fmt_vel="%s.velocity = %.15g mps\\0A\\00"
    # LLVM IR string constants count decoded bytes, so use explicit lengths.
    pos_n=23; vel_n=25
    lines=[
        '; ModuleID = \'slang\'', 'source_filename = "slang"', '',
        f'@fmt_pos = private constant [{pos_n} x i8] c"{fmt_pos}"',
        f'@fmt_vel = private constant [{vel_n} x i8] c"{fmt_vel}"',
        f'@name_target = private constant [{len(t)+1} x i8] c"{t}\\00"',
        '', 'declare i32 @printf(ptr, ...)', '',
        'define i32 @main() {', 'entry:',
        f'  %x0 = fadd double 0.0, {c(x)}', f'  %v0 = fadd double 0.0, {c(v)}',
        f'  %mass = fadd double 0.0, {c(m)}', f'  %G = fadd double 0.0, {c(G)}',
        f'  %dt = fadd double 0.0, {c(step)}',
        '  br label %loop', 'loop:',
        '  %i = phi i64 [ 0, %entry ], [ %nexti, %body ]',
        '  %x = phi double [ %x0, %entry ], [ %xn, %body ]',
        '  %v = phi double [ %v0, %entry ], [ %vn, %body ]',
        f'  %cond = icmp ult i64 %i, {steps}',
        '  br i1 %cond, label %body, label %done', 'body:',
        '  %xx = fmul double %x, %x', '  %gm = fmul double %G, %mass',
        '  %acc = fdiv double %gm, %xx', '  %dv = fmul double %acc, %dt',
        '  %vn = fadd double %v, %dv', '  %dx = fmul double %vn, %dt',
        '  %xn = fadd double %x, %dx', '  %nexti = add i64 %i, 1',
        '  br label %loop', 'done:'
    ]
    curx='%x'; curv='%v'
    if remainder>1e-12:
        lines += [f'  %rem = fadd double 0.0, {c(remainder)}',
                  f'  %xxr = fmul double {curx}, {curx}', '  %gmr = fmul double %G, %mass',
                  '  %accr = fdiv double %gmr, %xxr', '  %dvr = fmul double %accr, %rem',
                  f'  %vr = fadd double {curv}, %dvr', '  %dxr = fmul double %vr, %rem',
                  f'  %xr = fadd double {curx}, %dxr']
        curx='%xr'; curv='%vr'
    if any(n==t and f=='position' for n,f in p.shows):
        lines.append(f'  %p = call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([{pos_n} x i8], ptr @fmt_pos, i64 0, i64 0), ptr getelementptr inbounds ([{len(t)+1} x i8], ptr @name_target, i64 0, i64 0), double {curx})')
    if any(n==t and f=='velocity' for n,f in p.shows):
        lines.append(f'  %vp = call i32 (ptr, ...) @printf(ptr getelementptr inbounds ([{vel_n} x i8], ptr @fmt_vel, i64 0, i64 0), ptr getelementptr inbounds ([{len(t)+1} x i8], ptr @name_target, i64 0, i64 0), double {curv})')
    lines += ['  ret i32 0', '}', '']
    return '\n'.join(lines)

def slang_mlir(p:Program):
    """Emit a complete module containing the high-level registered S-Lang op.

    The result is valid input for the out-of-tree C++ dialect and can be lowered
    to standard MLIR and then to LLVM IR. The final print is an external runtime
    call so the same generated module can become a native executable.
    """
    validate(p)
    t, a, duration, step = p.simulation
    by = {b.name: b for b in p.bodies}
    tb, ab = by[t], by[a]
    x = tb.fields["position"].value
    v = tb.fields["velocity"].value
    m = ab.fields["mass"].value
    G = 6.67430e-11
    steps = int(math.floor(duration / step + 1e-12))
    def c(value):
        return f"0x{struct.unpack('Q', struct.pack('d', float(value)))[0]:016X}"
    out = [
        "module {",
        "  func.func @simulate() -> (f64, f64) {",
        f"    %x = arith.constant {c(x)} : f64",
        f"    %v = arith.constant {c(v)} : f64",
        f"    %mass = arith.constant {c(m)} : f64",
        f"    %G = arith.constant {c(G)} : f64",
        f"    %dt = arith.constant {c(step)} : f64",
        f"    %steps = arith.constant {steps} : index",
        '    %outx, %outv = "slang.simulate_gravity"(%x, %v, %mass, %G, %dt, %steps) : (f64, f64, f64, f64, f64, index) -> (f64, f64)',
        "    func.return %outx, %outv : f64, f64",
        "  }",
        "  func.func private @slang_print_result(%position: f64, %velocity: f64)",
        "  func.func @main() {",
        "    %position, %velocity = func.call @simulate() : () -> (f64, f64)",
    ]
    if any(n == t and f in {"position", "velocity"} for n, f in p.shows):
        out.append("    func.call @slang_print_result(%position, %velocity) : (f64, f64) -> ()")
    out += ["    func.return", "  }", "}", ""]
    return "\n".join(out)
