"""Runtime primitives used by the plan executor.

This module deliberately has no dependency on ``core``.  It contains the small
runtime value/quantity/domain helpers needed by the plan expression evaluator.
The reference interpreter keeps its own compatibility definitions in core.py.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
from .types import Type, ANY, RECORD, list_type, record_type, entity_type, type_from_ref, function_type, function_params, function_result, function_effects
from .domains import build_default_registry
from .stdlib.registry import get as get_stdlib_function

UNIT_DIM = {
    "kg": (1,0,0), "m": (0,1,0), "m2": (0,2,0), "s": (0,0,1), "mps": (0,1,-1),
    "m3_per_kg_s2": (-1,3,-2), "mps2": (0,1,-2), "N": (1,1,-2),
}
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
        if d == dim: return u
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
    dim=dim_add(a.dim(),b.dim()); return Quantity(a.value*b.value, unit_for_dim(dim) or f"<dim:{dim}>")
def qdiv(a,b):
    # Keep the same actionable message in the reference and planned runtimes.
    divisor = b if isinstance(b, (int, float)) else getattr(b, "value", None)
    if divisor == 0:
        raise ZeroDivisionError("division by zero: the divisor must be non-zero")
    if isinstance(a,(int,float)) and isinstance(b,(int,float)): return a/b
    if isinstance(b,(int,float)): return Quantity(a.value/b,a.unit)
    if isinstance(a,(int,float)):
        dim=tuple(-x for x in b.dim()); return Quantity(a/b.value, unit_for_dim(dim) or f"<dim:{dim}>")
    dim=dim_sub(a.dim(),b.dim()); return Quantity(a.value/b.value, unit_for_dim(dim) or f"<dim:{dim}>")
def pow2(q):
    dim=tuple(2*x for x in q.dim()); return Quantity(q.value*q.value, unit_for_dim(dim) or f"<dim:{dim}>")

@dataclass
class UserEntity:
    type_name: str
    name: str
    fields: dict[str, object]

class FunctionValue:
    def __init__(self, decl, program, closure=None):
        self.decl, self.program, self.closure = decl, program, closure
    @property
    def name(self): return self.decl.name
    def __call__(self, args):
        raise RuntimeError("reference function value cannot execute in plan runtime")

class ComposedFunctionValue(FunctionValue):
    def __init__(self, outer, inner):
        self.outer, self.inner = outer, inner
        self.decl = None
        self.program = getattr(outer, "program", None)
        self.closure = None
    @property
    def name(self): return "compose"
    def __call__(self, args):
        if len(args) != 1: raise TypeError("composed function expects 1 argument")
        return self.outer([self.inner([args[0]])])

def _is_function_value(value):
    return isinstance(value, (FunctionValue, ComposedFunctionValue))

class RecordValue(dict):
    def __init__(self, type_name: str | None, values: dict[str, object]):
        super().__init__(values); self.type_name = type_name

@dataclass
class Body:
    name: str
    fields: dict[str,Quantity]

@dataclass(frozen=True)
class Circle:
    name: str
    radius: Quantity

@dataclass(frozen=True)
class GraphPath:
    nodes: tuple[str, ...]
    cost: float

DOMAIN_REGISTRY = None
def domain_registry():
    global DOMAIN_REGISTRY
    if DOMAIN_REGISTRY is None:
        DOMAIN_REGISTRY = build_default_registry(Quantity, lambda name: Type(name), lambda name: entity_type(name), UNIT_DIM)
    return DOMAIN_REGISTRY

def type_name_for_value(value):
    if isinstance(value, RecordValue): return value.type_name or "Record"
    if isinstance(value, UserEntity): return value.type_name
    if isinstance(value, Body): return "Body"
    if isinstance(value, Circle): return "Circle"
    if isinstance(value, dict): return "Row"
    return type(value).__name__

def _resolve_runtime_type_ref(ref, program=None):
    if ref is None: return ANY
    records={r.name for r in getattr(getattr(program,'ast',None),'records',())}
    entities={e.name for e in getattr(getattr(program,'ast',None),'entities',())}
    generic_names=set()
    def resolve(r):
        if r.name == 'List': return list_type(resolve(r.args[0]) if r.args else ANY)
        if r.name == 'Record': return RECORD if not r.args else Type('Record', args=(resolve(r.args[0]),))
        if r.name == 'Entity': return Type('Entity') if not r.args else Type('Entity', args=(resolve(r.args[0]),))
        if r.name in records: return record_type(r.name, tuple(resolve(a) for a in r.args)) if r.args else record_type(r.name)
        if r.name in entities: return entity_type(r.name)
        if r.name == 'Function':
            effects={'pure','state-read','state-write','io','external'}
            raw=list(r.args); eff=[]
            while raw and not raw[-1].args and (raw[-1].name in effects or raw[-1].name in generic_names): eff.insert(0, raw.pop().name)
            vals=[resolve(a) for a in raw]
            return function_type(vals[:-1], vals[-1], tuple(eff) if eff else None) if vals else Type('Function')
        try: return type_from_ref(r)
        except Exception: return ANY
    return resolve(ref)

def _runtime_function_type(value):
    if isinstance(value, FunctionValue) and value.decl is not None:
        params=[_resolve_runtime_type_ref(ref, value.program) for _,ref in value.decl.parameters]
        result=_resolve_runtime_type_ref(value.decl.return_type, value.program)
        effects=getattr(value.decl, 'effects', None)
        return function_type(params,result,effects)
    if isinstance(value, ComposedFunctionValue):
        inner_t=_runtime_function_type(value.inner); outer_t=_runtime_function_type(value.outer)
        ie,oe=function_effects(inner_t),function_effects(outer_t)
        effects=None if ie is None or oe is None else tuple(sorted(set(ie)|set(oe)))
        return function_type((function_params(inner_t)[0],),function_result(outer_t),effects)
    raise TypeError('value is not a Function')

def _resolve_io_path(p, raw_path):
    from pathlib import Path
    path=Path(raw_path)
    if not path.is_absolute() and getattr(p,'base_dir',None) is not None: path=Path(p.base_dir)/path
    return path

def parse_quantity(text):
    m=re.match(r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s+([A-Za-z0-9_]+)$", text.strip())
    if not m: raise ValueError(f"invalid quantity: {text}")
    unit=m.group(2)
    if unit not in UNIT_DIM: raise ValueError(f"unknown unit '{unit}'")
    return Quantity(float(m.group(1)),unit)

def _goal_distance(candidate, target):
    if isinstance(candidate, UserEntity) and isinstance(target, UserEntity):
        if candidate.type_name != target.type_name: raise TypeError(f"goal target type mismatch: {candidate.type_name} vs {target.type_name}")
        if tuple(candidate.fields) != tuple(target.fields): raise TypeError("goal target structured state fields do not match")
        return sum(_goal_distance(candidate.fields[n], target.fields[n]) for n in candidate.fields)
    if isinstance(candidate, dict) and isinstance(target, dict):
        if tuple(candidate) != tuple(target): raise TypeError("goal target structured fields do not match")
        return sum(_goal_distance(candidate[n], target[n]) for n in candidate)
    if isinstance(candidate,(int,float)) and isinstance(target,(int,float)): return abs(candidate-target)
    if isinstance(candidate,Quantity) and isinstance(target,Quantity):
        if candidate.dim()!=target.dim(): raise TypeError("goal target quantities must have matching dimensions")
        return abs(candidate.value-target.value)
    raise TypeError(f"goal-directed distance is not defined for {type(candidate).__name__} and {type(target).__name__}")
