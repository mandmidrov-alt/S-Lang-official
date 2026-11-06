from types import SimpleNamespace

from slang.segment_bridge import SegmentDataContract, build_segment_data_contracts, capture, execute_reference_segment
from slang.execution_ir import ExecutionIR, ExecutionNode


def _ir():
    return ExecutionIR((
        ExecutionNode("a", "binding", "a", (), (), True),
        ExecutionNode("b", "filter", "b", ("a",), (), True),
        ExecutionNode("c", "binding", "c", ("b",), (), True),
    ))


def test_contract_contains_only_cross_segment_values():
    segments = (
        SimpleNamespace(index=0, nodes=("a",), mode="plan-runtime"),
        SimpleNamespace(index=1, nodes=("b",), mode="reference-interpreter"),
        SimpleNamespace(index=2, nodes=("c",), mode="plan-runtime"),
    )
    edges = (
        SimpleNamespace(before="a", after="b"),
        SimpleNamespace(before="b", after="c"),
    )
    contracts = build_segment_data_contracts(segments, edges, _ir())
    assert contracts[1].inputs == ("a",)
    assert contracts[1].outputs == ("b",)
    assert contracts[0].outputs == ("a",)


def test_reference_segment_does_not_receive_unrelated_namespace():
    module = SimpleNamespace(_bindings={"a": 2, "secret": 99}, _collections={}, _states={}, entities={},
                             _data_result_name=None, _data_result=None)
    segment = SimpleNamespace(index=1, mode="reference-interpreter", nodes=("b",))
    handoff = capture(module, 1, segment.mode, SegmentDataContract(inputs=("a",), outputs=("b",)))
    seen = {}
    def adapter(isolated, segment, handoff):
        seen.update(isolated._bindings)
        isolated._bindings["b"] = isolated._bindings["a"] + 1
    execute_reference_segment(module, segment, handoff, adapter)
    assert seen == {"a": 2}
    assert module._bindings == {"a": 2, "secret": 99, "b": 3}
