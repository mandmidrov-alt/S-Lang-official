from slang.core import parse, validate, run, register_domain, domain_registry
from slang.domains import DomainSpec, DomainFunction
from slang.types import quantity_type, entity_type
from slang.core import Quantity, UNIT_DIM


def test_standard_domain_registry_has_geometry_and_physics():
    reg = domain_registry()
    assert "geometry" in reg.domains
    assert "physics" in reg.domains
    assert "Circle" in reg.entities
    assert "Body" in reg.entities
    assert reg.function("distance") is not None


def test_circle_semantics_are_registry_driven():
    p = parse("""
circle c:
    radius 2 m
show c.area, c.circumference
""")
    run(p)
    assert p._circle_results[("c", "area")].unit == "m2"


def test_external_domain_can_extend_core_without_core_changes():
    d = DomainSpec(name="test_domain")
    d.entities["MeterBox"] = {"value": quantity_type(UNIT_DIM["m"])}
    d.properties["MeterBox"] = {"value": quantity_type(UNIT_DIM["m"])}
    d.property_evaluators[("MeterBox", "value")] = lambda box: box.fields["value"]
    d.functions["double_length"] = DomainFunction(
        "double_length", (quantity_type(UNIT_DIM["m"]),), quantity_type(UNIT_DIM["m"]),
        lambda args: Quantity(args[0].value * 2, "m"),
    )
    register_domain(d)
    p = parse("""
entity Sample:
    value: m

let x = Sample(3 m)
show double_length(x.value)
""")
    validate(p)
    run(p)
