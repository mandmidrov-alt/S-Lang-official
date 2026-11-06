from types import SimpleNamespace
import pytest

from slang.segment_bridge import SegmentDataContract, _state_snapshot, validate_runtime_state_boundary


def test_runtime_state_boundary_accepts_declared_state_write():
    module = SimpleNamespace(_states={"x": 1, "y": 10})
    contract = SegmentDataContract(state_inputs=("x",), state_outputs=("x",))
    before = _state_snapshot(module._states, {"x", "y"})
    module._states["x"] = 2
    assert validate_runtime_state_boundary(module, contract, before, segment_index=1)


def test_runtime_state_boundary_rejects_undeclared_state_write():
    module = SimpleNamespace(_states={"x": 1, "y": 10})
    contract = SegmentDataContract(state_inputs=("x",), state_outputs=("x",))
    before = _state_snapshot(module._states, {"x", "y"})
    module._states["y"] = 11
    with pytest.raises(RuntimeError, match="undeclared runtime state"):
        validate_runtime_state_boundary(module, contract, before, segment_index=1)


def test_runtime_state_boundary_requires_input_and_output():
    module = SimpleNamespace(_states={"x": 1})
    contract = SegmentDataContract(state_inputs=("x",), state_outputs=("z",))
    before = _state_snapshot(module._states, {"x", "z"})
    with pytest.raises(RuntimeError, match="missing declared runtime state output"):
        validate_runtime_state_boundary(module, contract, before, segment_index=2)


def test_runtime_state_boundary_requires_existing_input():
    module = SimpleNamespace(_states={})
    contract = SegmentDataContract(state_inputs=("x",), state_outputs=())
    before = _state_snapshot(module._states, {"x"})
    with pytest.raises(RuntimeError, match="missing runtime state input"):
        validate_runtime_state_boundary(module, contract, before, segment_index=3)
