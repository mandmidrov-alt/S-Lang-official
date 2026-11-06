from pathlib import Path
import json

from slang.backend import compile_program, lower_backend_artifact
from slang.compiler_artifact import CompilerArtifact
from slang.core import parse_file


def _artifact():
    result = compile_program(parse_file(Path("examples/fused_reduce.sl")), backend="native")
    return CompilerArtifact.from_json(result.artifact.to_json())


def test_parameter_abi_descriptors_roundtrip_and_validate():
    artifact = _artifact()
    assert artifact.parameter_abi_descriptors
    for binding, kind, value_type, byte_size, fmt, encoding in artifact.parameter_abi_descriptors:
        assert binding and kind and value_type
        assert byte_size >= 0
        assert fmt == "canonical-json"
        assert encoding == "utf8"
    restored = CompilerArtifact.from_json(artifact.to_json())
    assert restored.parameter_abi_descriptors == artifact.parameter_abi_descriptors


def test_parameter_abi_descriptor_tampering_is_rejected():
    artifact = _artifact()
    manifest = artifact.manifest()
    manifest["parameter_abi_descriptors"][0][3] += 1
    with __import__("pytest").raises(ValueError, match="fingerprint mismatch"):
        CompilerArtifact.from_manifest(manifest)


def test_mlir_emits_checked_parameter_descriptor_metadata():
    artifact = _artifact()
    text = lower_backend_artifact(artifact, backend="mlir").text
    assert "parameter-abi type=" in text
    assert "format=canonical-json" in text
    assert "encoding=utf8" in text
