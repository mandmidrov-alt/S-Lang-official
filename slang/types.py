from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class Type:
    name: str
    args: tuple['Type', ...] = ()
    dimension: Optional[tuple[int,int,int]] = None
    # Function effect contract. None means unspecified; () means pure.
    effects: Optional[tuple[str, ...]] = None

    def __str__(self):
        if self.name == 'Quantity' and self.dimension is not None:
            return f'Quantity<{self.dimension}>'
        if self.args:
            inner = ', '.join(map(str, self.args))
            if self.name == 'Function' and self.effects is not None:
                inner = inner + (', ' if inner else '') + ', '.join(self.effects or ('pure',))
            return f"{self.name}<" + inner + '>'
        return self.name

NUMBER = Type('Number')
BOOLEAN = Type('Boolean')
TEXT = Type('Text')
ANY = Type('Any')
RECORD = Type('Record')


@dataclass(frozen=True)
class FieldSchema:
    name: str
    type_name: str


@dataclass(frozen=True)
class RecordSchema:
    name: str
    fields: tuple[FieldSchema, ...] = ()

    def field(self, name: str):
        return next((f for f in self.fields if f.name == name), None)


def record_schema(name: str, fields) -> RecordSchema:
    return RecordSchema(name, tuple(FieldSchema(field, str(typ)) for field, typ in fields))


def quantity_type(dim):
    return Type('Quantity', dimension=tuple(dim))


def type_var(name: str) -> Type:
    return Type(name)


def is_type_var(t: Type) -> bool:
    return t.name.startswith('$') and not t.args


def contains_type_var(t: Type, names=None) -> bool:
    """Return whether a type contains a generic type variable.

    ``names`` may restrict the check to a concrete set such as the type
    parameters declared by one function. This is used by semantic analysis
    to reject generic signatures whose type parameters cannot be determined
    from call arguments.
    """
    if names is None:
        names = None
    if is_type_var(t):
        return names is None or t.name in names
    if t.name == 'Function' and t.effects:
        if any((names is None or effect in names) for effect in t.effects if is_effect_var_name(effect)):
            return True
    return any(contains_type_var(arg, names) for arg in t.args)


def list_type(item=ANY):
    return Type('List', args=(item,))


def list_element(t: Type) -> Type:
    if not is_list(t):
        raise TypeError(f'{t} is not a List type')
    return t.args[0]




_EFFECT_NAMES = {"pure", "state-read", "state-write", "io", "external"}


def is_effect_type_var(name: str) -> bool:
    return is_effect_var_name(name)


def normalize_effects(effects):
    """Return a deterministic effect contract.

    ``None`` means unknown/polymorphic and ``()`` means explicitly pure.
    Concrete effects are canonicalized so all type operations compare them
    structurally rather than depending on declaration order.
    """
    if effects is None:
        return None
    return tuple(sorted(set(effects)))


def effect_contract_compatible(expected, actual, bindings=None) -> bool:
    """Check effect-contract assignability and bind polymorphic effects.

    A function requiring a weaker contract may accept a function with fewer
    effects, while a pure requirement rejects an IO function. Effect variables
    are unified with the complete concrete effect set.
    """
    bindings = {} if bindings is None else bindings
    if expected is None or actual is None:
        return expected is None or actual is None or expected == actual
    expected = normalize_effects(expected)
    actual = normalize_effects(actual)
    expected_set = set(expected)
    actual_set = set(actual)
    expected_vars = [e for e in expected if is_effect_var_name(e)]
    actual_vars = [e for e in actual if is_effect_var_name(e)]
    fixed_expected = expected_set - set(expected_vars)

    # A concrete requirement can instantiate a polymorphic actual function.
    if actual_vars and not expected_vars:
        for var in actual_vars:
            previous = bindings.get(var)
            if previous is not None and effect_set_from_type(previous) != expected:
                return False
            bindings[var] = effect_set_type(expected)
        return fixed_expected.issuperset(actual_set - set(actual_vars))

    if not expected_vars:
        return actual_set.issubset(fixed_expected)

    concrete = effect_set_type(actual)
    for var in expected_vars:
        previous = bindings.get(var)
        if previous is not None and effect_set_from_type(previous) != actual:
            return False
        bindings[var] = concrete
    return actual_set.issuperset(fixed_expected)


def unify_types(expected: Type, actual: Type, bindings=None) -> bool:
    """Unified recursive type compatibility used by generic inference.

    The same operation handles ordinary type variables, nested generic
    containers, function parameters/results, and function effect variables.
    """
    bindings = {} if bindings is None else bindings
    if is_type_var(expected):
        previous = bindings.get(expected.name)
        if previous is None:
            if actual == expected:
                return True
            bindings[expected.name] = actual
            return True
        if previous == expected or previous == actual:
            return True
        return unify_types(previous, actual, bindings)
    if is_type_var(actual):
        previous = bindings.get(actual.name)
        if previous is None:
            if expected == actual:
                return True
            bindings[actual.name] = expected
            return True
        if previous == actual or previous == expected:
            return True
        return unify_types(expected, previous, bindings)
    if expected.name == 'Any' or actual.name == 'Any':
        return True
    # `Record` without a type parameter is the structural base record type;
    # it accepts any named/parameterized record. This keeps generic APIs such
    # as List<Record> usable with List<Record<Person>> without making named
    # records indistinguishable from one another.
    if expected.name == 'Record' and actual.name == 'Record' and not expected.args:
        return True
    if expected.name != actual.name or len(expected.args) != len(actual.args):
        return False
    if expected.name == 'Quantity' and expected.dimension != actual.dimension:
        return False
    if expected.name == 'Function':
        if not effect_contract_compatible(expected.effects, actual.effects, bindings):
            return False
    return all(unify_types(e, a, bindings) for e, a in zip(expected.args, actual.args))


def generic_match(expected: Type, actual: Type, bindings=None) -> bool:
    return unify_types(expected, actual, bindings)


def substitute_type(t: Type, bindings: dict[str, Type]) -> Type:
    if is_type_var(t):
        value = bindings.get(t.name)
        if value is None:
            return ANY
        if value == t:
            return t
        return substitute_type(value, bindings)
    if not t.args:
        effects = t.effects
        if t.name == 'Function' and effects is not None:
            resolved = []
            for effect in effects:
                bound = bindings.get(effect)
                concrete = effect_set_from_type(bound) if bound is not None else None
                if concrete is not None:
                    resolved.extend(concrete)
                else:
                    resolved.append(effect)
            return Type(t.name, args=t.args, dimension=t.dimension, effects=tuple(sorted(set(resolved))))
        return t
    effects = t.effects
    if t.name == 'Function' and effects is not None:
        resolved = []
        for effect in effects:
            bound = bindings.get(effect)
            concrete = effect_set_from_type(bound) if bound is not None else None
            if concrete is not None:
                resolved.extend(concrete)
            else:
                resolved.append(effect)
        effects = tuple(sorted(set(resolved)))
    return Type(t.name, args=tuple(substitute_type(a, bindings) for a in t.args), dimension=t.dimension, effects=effects)


def function_type(params, result, effects=None):
    effects = normalize_effects(effects)
    return Type('Function', args=tuple(params) + (result,), effects=effects)


def is_effect_var_name(name: str) -> bool:
    return isinstance(name, str) and name.startswith('$') and len(name) > 1 and name[1:].isupper()


def effect_set_type(effects) -> Type:
    return Type('EffectSet', args=tuple(Type(str(e)) for e in effects))


def effect_set_from_type(t: Type):
    if t.name != 'EffectSet':
        return None
    return tuple(a.name for a in t.args)


def function_effects(t: Type) -> Optional[tuple[str, ...]]:
    if not is_function(t):
        raise TypeError(f'{t} is not a Function type')
    return t.effects


def with_function_effects(t: Type, effects) -> Type:
    if not is_function(t):
        raise TypeError(f'{t} is not a Function type')
    return function_type(function_params(t), function_result(t), effects)


def is_function(t: Type) -> bool:
    return t.name == 'Function' and len(t.args) >= 1


def function_result(t: Type) -> Type:
    if not is_function(t):
        raise TypeError(f'{t} is not a Function type')
    return t.args[-1]


def function_params(t: Type):
    if not is_function(t):
        raise TypeError(f'{t} is not a Function type')
    return t.args[:-1]


def entity_type(name):
    return Type('Entity', args=(Type(name),))

def record_type(name, args=()):
    if args:
        return Type('Record', args=(Type(name, args=tuple(args)),))
    return Type('Record', args=(Type(name),))

def entity_name(t):
    if t.name == 'Entity' and t.args:
        return t.args[0].name
    return None


def is_numeric(t):
    return t.name in ('Number', 'Quantity')


def same_or_any(a: Type, b: Type) -> bool:
    if a == b or a.name == 'Any' or b.name == 'Any': return True
    if is_type_var(a) or is_type_var(b): return True
    if a.name == 'Function' and b.name == 'Function':
        if len(a.args) != len(b.args): return False
        if a.effects is not None:
            if b.effects is None or not set(b.effects).issubset(set(a.effects)):
                return False
        return all(same_or_any(x, y) for x, y in zip(a.args, b.args))
    if a.name == 'List' and b.name == 'List' and len(a.args) == len(b.args) == 1:
        return same_or_any(a.args[0], b.args[0])
    if a.name == 'Record' and b.name == 'Record':
        # Bare Record is the structural supertype of all named records.
        if not a.args or not b.args: return True
    return False

def is_list(t: Type) -> bool:
    return t.name == 'List' and len(t.args) == 1

def list_item_type(t: Type) -> Type:
    if not is_list(t):
        raise TypeError(f'{t} is not a List type')
    return t.args[0]


def collection_preserve_type(source: Type) -> Type:
    """Return the element-preserving type of a collection operation."""
    if not is_list(source):
        raise TypeError(f'{source} is not a List type')
    return list_type(list_item_type(source))


def collection_map_type(source: Type, mapped: Type) -> Type:
    """Infer the result of mapping one element type to another."""
    if not is_list(source):
        raise TypeError(f'{source} is not a List type')
    return list_type(mapped)


def collection_reduce_type(accumulator: Type) -> Type:
    """A reduce expression has the type of its accumulator."""
    return accumulator


def add_types(a: Type, b: Type) -> Type:
    if a.name == 'Number' and b.name == 'Number': return NUMBER
    if a.name == 'Text' and b.name == 'Text': return TEXT
    if a.name == 'Quantity' and b.name == 'Quantity' and a.dimension == b.dimension:
        return quantity_type(a.dimension)
    raise TypeError(f'cannot add {a} and {b}')


def sub_types(a: Type, b: Type) -> Type:
    if a.name == 'Number' and b.name == 'Number': return NUMBER
    if a.name == 'Quantity' and b.name == 'Quantity' and a.dimension == b.dimension:
        return quantity_type(a.dimension)
    raise TypeError(f'cannot subtract {a} and {b}')


def mul_types(a: Type, b: Type) -> Type:
    if a.name == 'Number': return b
    if b.name == 'Number': return a
    if a.name == 'Quantity' and b.name == 'Quantity':
        return quantity_type(tuple(x+y for x,y in zip(a.dimension, b.dimension)))
    raise TypeError(f'cannot multiply {a} and {b}')


def div_types(a: Type, b: Type) -> Type:
    if b.name == 'Number': return a
    if a.name == 'Number' and b.name == 'Quantity':
        return quantity_type(tuple(-x for x in b.dimension))
    if a.name == 'Quantity' and b.name == 'Quantity':
        return quantity_type(tuple(x-y for x,y in zip(a.dimension, b.dimension)))
    raise TypeError(f'cannot divide {a} by {b}')


def type_from_ref(ref):
    if ref is None: return ANY
    name = ref.name if hasattr(ref, 'name') else str(ref)
    args = tuple(type_from_ref(a) for a in getattr(ref, 'args', ()))
    if name == 'Number': return NUMBER
    if name == 'Boolean': return BOOLEAN
    if name == 'Text': return TEXT
    if name == 'Record':
        return RECORD if not args else Type('Record', args=args)
    if name == 'List':
        return list_type(args[0] if args else ANY)
    if name == 'Entity':
        return Type('Entity', args=args) if args else Type('Entity')
    if name == 'Function':
        if not args: return Type('Function')
        effect_names = {'pure', 'state-read', 'state-write', 'io', 'external'}
        raw = getattr(ref, 'args', ())
        effects = None
        if len(raw) >= 2 and all(getattr(a, 'name', '') in effect_names and not getattr(a, 'args', ()) for a in raw[-1:]):
            # A trailing effect marker is part of the function contract.
            markers = []
            while raw and raw[-1].name in effect_names and not raw[-1].args:
                markers.insert(0, raw[-1].name); raw = raw[:-1]
            if markers:
                effects = tuple(markers)
                args = tuple(type_from_ref(a) for a in raw)
        return function_type(args[:-1], args[-1], effects) if len(args) >= 1 else Type('Function')
    unit_dims = {
        'kg': (1,0,0), 'm': (0,1,0), 'm2': (0,2,0), 's': (0,0,1),
        'mps': (0,1,-1), 'mps2': (0,1,-2), 'N': (1,1,-2),
        'm3_per_kg_s2': (-1,3,-2),
    }
    if name in unit_dims: return quantity_type(unit_dims[name])
    # User-defined type names are represented uniformly as Entity<T> values.
    if name and name[0].isupper(): return entity_type(name)
    return Type(name)
