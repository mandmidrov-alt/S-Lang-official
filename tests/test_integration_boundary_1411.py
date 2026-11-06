import json
from pathlib import Path

import pytest

from slang.backend import compile_program, lower_backend_artifact
from slang.compiler_artifact import CompilerArtifact
from slang.core import parse_file
from slang.runtime_parameter_abi import build_runtime_parameter_table, validate_runtime_call_parameter
from slang.stdlib_runtime import execute_runtime_call


SOURCE = Path("examples/fused_reduce.sl")


def test_complete_114_boundary_survives_persisted_artifact_roundtrip():
    result = compile_program(parse_file(SOURCE), backend="native")
    artifact = CompilerArtifact.from_json(result.artifact.to_json())

    assert artifact.fingerprint == result.artifact.fingerprint
    assert artifact.to_json() == result.artifact.to_json()
    assert artifact.selected_execution_plan is not None
    assert artifact.operation_contract
    assert artifact.parameter_materialization
    assert artifact.parameter_abi_descriptors

    table = build_runtime_parameter_table(artifact)
    assert set(table) == {entry[0] for entry in artifact.parameter_materialization}

    binding, kind, _, seed = artifact.parameter_materialization[0]
    descriptor = validate_runtime_call_parameter(
        artifact,
        binding,
        operation_kind=kind,
        descriptor_seed=int(seed),
    )
    assert descriptor.seed == int(seed)

    native = lower_backend_artifact(artifact, backend="native")
    mlir = lower_backend_artifact(artifact, backend="mlir")
    assert native.format == "llvm-ir"
    assert native.executable is True
    assert "define" in native.text
    assert mlir.format == "mlir"
    assert artifact.fingerprint in mlir.text
    assert "parameter-abi type=" in mlir.text

    handled, value = execute_runtime_call(
        "filter_values",
        [[1, 2, 3]],
        lambda args: [x for x in args[0] if x > 1],
        expected_args=1,
        artifact=artifact,
        parameter_binding=binding,
        parameter_seed=descriptor.seed,
        parameter_value_type=descriptor.value_type,
        parameter_byte_size=descriptor.byte_size,
        parameter_operation_kind=kind,
    )
    assert handled is True
    assert value == [2, 3]


def test_complete_114_boundary_is_deterministic_across_recompilation():
    first = compile_program(parse_file(SOURCE), backend="native")
    second = compile_program(parse_file(SOURCE), backend="native")

    assert first.artifact.fingerprint == second.artifact.fingerprint
    assert first.artifact.to_json() == second.artifact.to_json()
    assert first.lowered.text == second.lowered.text
    assert lower_backend_artifact(first.artifact, backend="mlir").text == lower_backend_artifact(
        second.artifact, backend="mlir"
    ).text


def test_complete_114_boundary_rejects_manifest_tampering():
    result = compile_program(parse_file(SOURCE), backend="native")
    manifest = json.loads(result.artifact.to_json())
    manifest["parameter_abi_descriptors"][0][3] += 1

    with pytest.raises(ValueError, match="fingerprint mismatch"):
        CompilerArtifact.from_manifest(manifest)
