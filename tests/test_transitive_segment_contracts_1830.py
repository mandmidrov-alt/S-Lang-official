from types import SimpleNamespace

from slang.execution_ir import ExecutionIR, ExecutionNode
from slang.segment_bridge import build_segment_data_contracts, validate_segment_contracts


def _ir():
    return ExecutionIR((
        ExecutionNode("a", "binding", "a", (), (), True),
        ExecutionNode("b", "binding", "b", (), (), True),
        ExecutionNode("c", "binding", "c", ("a",), (), True),
    ))


def _segments():
    return (
        SimpleNamespace(index=0, nodes=("a",), mode="plan-runtime"),
        SimpleNamespace(index=1, nodes=("b",), mode="reference-interpreter"),
        SimpleNamespace(index=2, nodes=("c",), mode="plan-runtime"),
    )


def test_transitive_value_is_forwarded_through_intermediate_segment():
    segments = _segments()
    edges = (SimpleNamespace(before="a", after="c", kind="value"),)
    contracts = build_segment_data_contracts(segments, edges, _ir())
    assert contracts[0].outputs == ("a",)
    assert contracts[1].inputs == ("a",)
    assert contracts[1].outputs == ("a",)
    assert contracts[2].inputs == ("a",)


def test_transitive_contract_is_validated_before_execution():
    segments = _segments()
    edges = (SimpleNamespace(before="a", after="c", kind="value"),)
    contracts = build_segment_data_contracts(segments, edges, _ir())
    assert validate_segment_contracts(segments, contracts, edges, ir=_ir())
