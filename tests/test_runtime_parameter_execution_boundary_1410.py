import pytest

from slang.stdlib_runtime import execute_runtime_call
from slang.runtime_parameter_abi import validate_runtime_call_parameter


def _artifact():
    from pathlib import Path
    from slang.core import parse_file
    from slang.backend import compile_program
    return compile_program(parse_file(Path("examples/fused_reduce.sl")), backend="native").artifact

def test_parameter_is_validated_at_runtime_call_boundary():
    artifact = _artifact()
    binding = artifact.parameter_materialization[0][0]
    operation_kind = artifact.parameter_materialization[0][1]
    descriptor = validate_runtime_call_parameter(
        artifact,
        binding,
        operation_kind=artifact.parameter_materialization[0][1],
        descriptor_seed=artifact.parameter_materialization[0][3],
    )
    seen = {}

    handled, result = execute_runtime_call(
        "filter_values",
        [1],
        lambda values: seen.setdefault("values", values) or 7,
        expected_args=1,
        artifact=artifact,
        parameter_binding=binding,
        parameter_seed=descriptor.seed,
        parameter_value_type=descriptor.value_type,
        parameter_byte_size=descriptor.byte_size,
        parameter_operation_kind=operation_kind,
    )
    assert handled is True
    assert result == [1]


def test_runtime_call_rejects_tampered_parameter_seed():
    artifact = _artifact()
    binding, kind, _, seed = artifact.parameter_materialization[0]
    seed = int(seed)
    with pytest.raises(ValueError, match="seed mismatch"):
        execute_runtime_call(
            kind,
            [],
            lambda values: 1,
            artifact=artifact,
            parameter_binding=binding,
            parameter_seed=seed + 1,
            parameter_operation_kind=kind,
        )
