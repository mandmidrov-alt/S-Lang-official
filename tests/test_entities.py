import pytest
from slang.core import parse, validate, run, show_expr_value

def test_user_entity_is_a_real_typed_value():
    src = """entity Planet:
    mass: kg
    position: m
    velocity: mps

let earth = Planet(5.972e24 kg, 1.496e11 m, 29780 mps)
show earth.mass, earth.position
"""
    p=parse(src); validate(p); run(p)
    assert show_expr_value(p, p.show_exprs[0]) == '5.972e+24 kg'
    assert show_expr_value(p, p.show_exprs[1]) == '149600000000 m'


def test_user_entity_field_type_is_checked():
    src = """entity Planet:
    mass: kg
    position: m

let earth = Planet(5 m, 1 kg)
"""
    p=parse(src)
    with pytest.raises(TypeError, match="argument 1 of 'Planet' expects"):
        validate(p)


def test_user_entity_computed_property_uses_common_property_system():
    src = """entity Planet:
    radius: m

property Planet.diameter -> m:
    return self.radius * 2

let earth = Planet(6 m)
show earth.diameter
"""
    p=parse(src); validate(p); run(p)
    assert show_expr_value(p, p.show_exprs[0]) == '12 m'


def test_unknown_user_entity_field_is_rejected():
    src = """entity Planet:
    mass: kg

let earth = Planet(5 kg)
show earth.velocity
"""
    p=parse(src)
    with pytest.raises(TypeError, match="unknown field 'velocity'"):
        validate(p)


def test_user_entity_can_be_used_in_function():
    src = """entity Planet:
    mass: kg

function double_mass(p: Planet) -> kg:
    return p.mass * 2

let earth = Planet(5 kg)
show double_mass(earth)
"""
    p=parse(src); validate(p); run(p)
    assert show_expr_value(p, p.show_exprs[0]) == '10 kg'
