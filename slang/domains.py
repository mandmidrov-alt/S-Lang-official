"""Domain registry for S-Lang's semantic/runtime extensions.

The core language knows how to ask a domain for types, properties and function
implementations, but does not contain domain-specific cases.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Any

@dataclass
class DomainFunction:
    name: str
    parameters: tuple[Any, ...]
    result: Any
    evaluator: Callable[[list[Any]], Any]

@dataclass
class DomainSpec:
    name: str
    entities: dict[str, dict[str, Any]] = field(default_factory=dict)
    properties: dict[str, dict[str, Any]] = field(default_factory=dict)
    functions: dict[str, DomainFunction] = field(default_factory=dict)
    property_evaluators: dict[tuple[str, str], Callable[[Any], Any]] = field(default_factory=dict)

class DomainRegistry:
    def __init__(self):
        self.domains: dict[str, DomainSpec] = {}
        self.entities: dict[str, dict[str, Any]] = {}
        self.properties: dict[str, dict[str, Any]] = {}
        self.functions: dict[str, DomainFunction] = {}
        self.property_evaluators: dict[tuple[str, str], Callable[[Any], Any]] = {}

    def register(self, domain: DomainSpec):
        if domain.name in self.domains:
            raise ValueError(f"duplicate domain '{domain.name}'")
        self.domains[domain.name] = domain
        for name, fields in domain.entities.items():
            if name in self.entities:
                raise ValueError(f"duplicate domain entity '{name}'")
            self.entities[name] = fields
        for entity, props in domain.properties.items():
            self.properties.setdefault(entity, {}).update(props)
        for key, evaluator in domain.property_evaluators.items():
            self.property_evaluators[key] = evaluator
        for name, fn in domain.functions.items():
            if name in self.functions:
                raise ValueError(f"duplicate domain function '{name}'")
            self.functions[name] = fn
        return domain

    def entity_fields(self, name):
        return self.entities.get(name)

    def property_type(self, entity, name):
        return self.properties.get(entity, {}).get(name)

    def evaluate_property(self, entity, name, value):
        fn = self.property_evaluators.get((entity, name))
        if fn is None:
            raise KeyError((entity, name))
        return fn(value)

    def function(self, name):
        return self.functions.get(name)


def build_default_registry(Quantity, quantity_type, entity_type, UNIT_DIM):
    """Load standard domains as ordinary registry modules."""
    from .stdlib.geometry import make_domain as make_geometry
    from .stdlib.physics import make_domain as make_physics

    registry = DomainRegistry()
    registry.register(make_geometry(Quantity, quantity_type, UNIT_DIM))
    registry.register(make_physics(Quantity, quantity_type, entity_type, UNIT_DIM))
    return registry
