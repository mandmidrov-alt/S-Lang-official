from types import SimpleNamespace

from slang.segment_bridge import capture, restore, execute_reference_segment


def test_segment_handoff_preserves_runtime_namespace():
    module = SimpleNamespace(
        _bindings={"x": 3}, _collections={"rows": [1, 2]},
        _states={"counter": 4}, entities={"e": object()},
        _data_result_name="rows", _data_result=[1, 2]
    )
    handoff = capture(module, 1, "reference-interpreter")
    module._bindings["x"] = 99
    module._collections["rows"].append(3)
    restore(module, handoff)
    assert module._bindings == {"x": 3}
    assert module._collections == {"rows": [1, 2]}
    assert module._states == {"counter": 4}
    assert module._data_result_name == "rows"


def test_reference_segment_requires_explicit_adapter():
    segment = SimpleNamespace(index=2, mode="reference-interpreter", nodes=("unsupported",))
    handoff = capture(SimpleNamespace(), 2, "reference-interpreter")
    try:
        execute_reference_segment(SimpleNamespace(), segment, handoff)
    except RuntimeError as exc:
        assert "explicit fallback adapter" in str(exc)
    else:
        raise AssertionError("missing segment adapter must be rejected")


def test_reference_segment_mutates_shared_module():
    module = SimpleNamespace(_bindings={"x": 1})
    segment = SimpleNamespace(index=0, mode="reference-interpreter", nodes=("unsupported",))
    handoff = capture(module, 0, "reference-interpreter")

    def adapter(shared, current, boundary):
        assert current is segment
        assert boundary.bindings["x"] == 1
        shared._bindings["x"] = 2

    execute_reference_segment(module, segment, handoff, adapter)
    assert module._bindings["x"] == 2
