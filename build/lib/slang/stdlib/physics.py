from __future__ import annotations
from ..domains import DomainSpec, DomainFunction

def make_domain(Quantity, quantity_type, entity_type, UNIT_DIM):
    d = DomainSpec(name="physics")
    d.entities["Body"] = {
        "mass": quantity_type(UNIT_DIM["kg"]),
        "position": quantity_type(UNIT_DIM["m"]),
        "velocity": quantity_type(UNIT_DIM["mps"]),
    }
    d.properties["Body"] = dict(d.entities["Body"])
    d.functions["distance"] = DomainFunction(
        "distance", (entity_type("Body"), entity_type("Body")),
        quantity_type(UNIT_DIM["m"]),
        lambda args: Quantity(abs(args[0].fields["position"].value - args[1].fields["position"].value), "m"),
    )
    return d
