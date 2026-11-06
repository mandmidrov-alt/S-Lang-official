from __future__ import annotations
import math
from ..domains import DomainSpec

def make_domain(Quantity, quantity_type, UNIT_DIM):
    d = DomainSpec(name="geometry")
    d.entities["Circle"] = {"radius": quantity_type(UNIT_DIM["m"])}
    d.properties["Circle"] = {
        "radius": quantity_type(UNIT_DIM["m"]),
        "area": quantity_type(UNIT_DIM["m2"]),
        "circumference": quantity_type(UNIT_DIM["m"]),
    }
    d.property_evaluators.update({
        ("Circle", "radius"): lambda c: c.radius,
        ("Circle", "area"): lambda c: Quantity(math.pi * c.radius.value**2, "m2"),
        ("Circle", "circumference"): lambda c: Quantity(2 * math.pi * c.radius.value, "m"),
    })
    return d
