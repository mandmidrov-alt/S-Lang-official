from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class Expr: pass

@dataclass(frozen=True)
class Literal(Expr):
    value: Any

@dataclass(frozen=True)
class Name(Expr):
    name: str

@dataclass(frozen=True)
class Field(Expr):
    base: Expr
    name: str

@dataclass(frozen=True)
class Binary(Expr):
    op: str
    left: Expr
    right: Expr

@dataclass(frozen=True)
class Compare(Expr):
    op: str
    left: Expr
    right: Expr

@dataclass(frozen=True)
class Logical(Expr):
    op: str
    left: Expr
    right: Expr | None = None

@dataclass(frozen=True)
class Conditional(Expr):
    condition: Expr
    then_expr: Expr
    else_expr: Expr

@dataclass(frozen=True)
class Call(Expr):
    name: str
    args: tuple[Expr, ...] = ()

@dataclass(frozen=True)
class Property(Expr):
    base: Expr
    name: str

@dataclass(frozen=True)
class ReturnOp:
    expr: Expr

@dataclass(frozen=True)
class LetOp:
    name: str
    expr: Expr

@dataclass(frozen=True)
class IfOp:
    condition: Expr
    then_body: list[object] = field(default_factory=list)
    else_body: list[object] = field(default_factory=list)

@dataclass(frozen=True)
class LocalCollectionOp:
    """Collection transformation evaluated in a lexical block/function scope."""
    name: str
    source: str
    stages: tuple[tuple[str, Expr | None, Expr | None, str | None], ...]

@dataclass
class FunctionDecl:
    name: str
    parameters: list[tuple[str, 'TypeRef | None']] = field(default_factory=list)
    return_type: 'TypeRef | None' = None
    body: list[object] = field(default_factory=list)
    type_params: tuple[str, ...] = ()

@dataclass
class EntityDecl:
    name: str
    fields: list[tuple[str, 'TypeRef']] = field(default_factory=list)

@dataclass
class RecordDecl:
    name: str
    fields: list[tuple[str, 'TypeRef']] = field(default_factory=list)
    type_params: tuple[str, ...] = ()

@dataclass(frozen=True)
class BindingDecl:
    name: str
    expr: Expr

@dataclass(frozen=True)
class StateDecl:
    name: str
    expr: Expr

@dataclass(frozen=True)
class SetStateOp:
    name: str
    expr: Expr

@dataclass
class PropertyDecl:
    entity_type: str
    name: str
    return_type: 'TypeRef | None' = None
    body: list[object] = field(default_factory=list)

@dataclass(frozen=True)
class TypeRef:
    name: str
    args: tuple['TypeRef', ...] = ()

@dataclass(frozen=True)
class ImportDecl:
    path: str
    alias: str | None = None
    names: tuple[str, ...] = ()

@dataclass(frozen=True)
class ModuleDecl:
    name: str

@dataclass(frozen=True)
class Predicate:
    expr: Expr

@dataclass(frozen=True)
class SortSpec:
    expr: Expr
    ascending: bool = True

@dataclass
class DataDecl:
    name: str
    rows: list[dict[str, Any]] = field(default_factory=list)

@dataclass
class BodyDecl:
    name: str
    fields: dict[str, Any] = field(default_factory=dict)

@dataclass
class CircleDecl:
    name: str
    fields: dict[str, Any] = field(default_factory=dict)

@dataclass
class FilterOp:
    source: str
    predicate: Predicate
    result: str

@dataclass
class SortOp:
    source: str
    spec: SortSpec
    result: str

@dataclass
class MapOp:
    source: str
    expr: Expr
    result: str

@dataclass
class AggregateOp:
    source: str
    operation: str
    expr: Expr
    result: str

@dataclass
class ReduceOp:
    source: str
    initial: Expr
    expr: Expr
    result: str

@dataclass
class ConditionalPipelineOp:
    source: str
    condition: Expr
    then_stages: tuple[tuple[str, object], ...]
    else_stages: tuple[tuple[str, object], ...]
    result: str

    @property
    def then_kind(self):
        return self.then_stages[0][0] if self.then_stages else None

    @property
    def then_expr(self):
        return self.then_stages[0][1] if self.then_stages else None

    @property
    def else_kind(self):
        return self.else_stages[0][0] if self.else_stages else None

    @property
    def else_expr(self):
        return self.else_stages[0][1] if self.else_stages else None

@dataclass
class SequenceOp:
    result: str
    initial: Expr
    steps: int
    expr: Expr
    until: Expr | None = None
    target: Expr | None = None
    candidates: tuple[Expr, ...] = ()
    constraint: Expr | None = None
    constraints: tuple[Expr, ...] = ()

@dataclass
class GoalOp:
    result: str
    source: str
    predicate: Predicate | None
    key: Expr
    direction: str

@dataclass
class GraphDecl:
    name: str
    edges: list[tuple[str, str, float, bool]] = field(default_factory=list)

@dataclass
class PathGoalOp:
    result: str
    source: str
    start: str
    end: str
    objective: str = 'cost'

@dataclass(frozen=True)
class SatisfyGoalOp:
    result: str
    variables: tuple[tuple[str, int, int], ...]
    constraints: tuple[Expr, ...]

@dataclass
class ShowOp:
    target: Expr

@dataclass
class SimulationOp:
    target: str
    attractor: str
    duration: float
    step: float

@dataclass
class Module:
    module: ModuleDecl | None = None
    imports: list[ImportDecl] = field(default_factory=list)
    gravity: bool = False
    bodies: list[BodyDecl] = field(default_factory=list)
    datasets: list[DataDecl] = field(default_factory=list)
    circles: list[CircleDecl] = field(default_factory=list)
    filters: list[FilterOp] = field(default_factory=list)
    sorts: list[SortOp] = field(default_factory=list)
    maps: list[MapOp] = field(default_factory=list)
    aggregates: list[AggregateOp] = field(default_factory=list)
    reduces: list[ReduceOp] = field(default_factory=list)
    conditional_pipelines: list[ConditionalPipelineOp] = field(default_factory=list)
    sequences: list[SequenceOp] = field(default_factory=list)
    goals: list[GoalOp] = field(default_factory=list)
    graphs: list[GraphDecl] = field(default_factory=list)
    path_goals: list[PathGoalOp] = field(default_factory=list)
    satisfy_goals: list[SatisfyGoalOp] = field(default_factory=list)
    simulations: list[SimulationOp] = field(default_factory=list)
    shows: list[ShowOp] = field(default_factory=list)
    functions: list[FunctionDecl] = field(default_factory=list)
    properties: list[PropertyDecl] = field(default_factory=list)
    entities: list[EntityDecl] = field(default_factory=list)
    records: list[RecordDecl] = field(default_factory=list)
    bindings: list[BindingDecl] = field(default_factory=list)
    states: list[StateDecl] = field(default_factory=list)
    state_sets: list[SetStateOp] = field(default_factory=list)
    ordered_effects: list[Any] = field(default_factory=list)
    # Executable top-level statements preserve source order for effects and control flow.
    top_level_statements: list[Any] = field(default_factory=list)
    module_exports: dict[str, dict[str, object]] = field(default_factory=dict)
    exports: tuple[str, ...] = ()
    reexports: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)


# Source locations are stored out-of-band so the long-lived AST dataclasses
# remain backwards-compatible with existing positional constructors.
_SOURCE_SPANS: dict[int, object] = {}
_SOURCE_NODES: dict[int, object] = {}

def mark_source_span(node, span):
    """Attach source metadata without changing the public AST constructors.

    The registry is intentionally out-of-band.  Existing callers may still
    construct AST nodes positionally, while parser-created trees can carry
    spans down to nested AST nodes.
    """
    if node is not None and span is not None:
        ident = id(node)
        _SOURCE_NODES[ident] = node
        _SOURCE_SPANS[ident] = span
    return node


def mark_source_span_tree(node, span, *, overwrite=False):
    """Attach ``span`` to every AST node below ``node``.

    Child nodes are filled only when they do not already have a more precise
    location.  This lets parser helpers attach a narrow span first and a
    statement-level span later without losing precision.
    """
    if node is None or span is None:
        return node
    seen = set()

    def visit(value):
        if value is None:
            return
        ident = id(value)
        if ident in seen:
            return
        seen.add(ident)
        if hasattr(value, "__dataclass_fields__"):
            _SOURCE_NODES[ident] = value
            if overwrite or ident not in _SOURCE_SPANS:
                _SOURCE_SPANS[ident] = span
            for name in value.__dataclass_fields__:
                visit(getattr(value, name))
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            for item in value.values():
                visit(item)

    visit(node)
    return node


def source_span_of(node):
    return _SOURCE_SPANS.get(id(node))

