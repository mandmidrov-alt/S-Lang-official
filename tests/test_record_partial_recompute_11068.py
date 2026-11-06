from types import SimpleNamespace

from slang.global_plan_optimizer import _record_partial_recompute_candidate


def _node():
    schema = SimpleNamespace(fields=(
        SimpleNamespace(name="score", type_name="Number"),
        SimpleNamespace(name="value", type_name="Text"),
        SimpleNamespace(name="name", type_name="Text"),
    ))
    parent = SimpleNamespace(
        kind="map", pure=True, deterministic=True, input_schema=schema, output_schema=schema,
        record_field_provenance=(("score", ("score",), "direct"),
                                 ("value", ("score",), "derived"),
                                 ("name", ("name",), "direct")),
    )
    child = SimpleNamespace(kind="map", pure=True, deterministic=True)
    return parent, child


def test_partial_recompute_preserves_source_fields_for_derived_output():
    parent, child = _node()
    ok, cost, detail = _record_partial_recompute_candidate(parent, child, ("value",))
    assert ok
    assert cost > 0
    assert detail == (("value", ("score",), 1.0),)


def test_partial_recompute_is_rejected_for_direct_or_unknown_fields():
    parent, child = _node()
    ok, _, _ = _record_partial_recompute_candidate(parent, child, ("score",))
    assert not ok
    parent.record_field_provenance = (("value", ("score",), "unknown"),)
