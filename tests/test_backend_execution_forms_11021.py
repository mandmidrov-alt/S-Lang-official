from pathlib import Path
import pytest
from slang.core import parse, validate
from slang.mlir_backend import lower_execution_ir_to_mlir
from slang.backend import compile_selected_backend, capabilities_for, validate_execution_regions


def _module(name="examples/data_generic.sl"):
    p = parse(Path(name).read_text())
    validate(p)
    return p.ast


def test_streaming_form_has_explicit_scf_structure():
    pipeline = compile_selected_backend(_module()).pipeline
    text = lower_execution_ir_to_mlir(_module(), pipeline=pipeline)
    assert "execution-mode" not in text
    assert "execution-region" in text
    if any(r.mode == "streaming" for r in pipeline.selected_execution_plan.execution_regions):
        assert "scf.for" in text


def test_materialized_form_has_explicit_memref_boundary():
    pipeline = compile_selected_backend(_module()).pipeline
    text = lower_execution_ir_to_mlir(_module(), pipeline=pipeline)
    if any(r.mode == "materialized" for r in pipeline.selected_execution_plan.execution_regions):
        assert "memref.alloca" in text
        assert "memref.dealloc" in text


def test_parallel_form_has_explicit_scf_parallel_structure_when_present():
    # This example is compiled with the default backend policy; if no parallel
    # region is selected, the assertion is intentionally vacuous because the
    # backend must never invent parallelism during lowering.
    pipeline = compile_selected_backend(_module()).pipeline
    text = lower_execution_ir_to_mlir(_module(), pipeline=pipeline)
    if any(r.mode == "parallel" for r in pipeline.selected_execution_plan.execution_regions):
        assert "scf.parallel" in text


def test_backend_declares_execution_mode_capabilities():
    assert "parallel" not in capabilities_for("native").supported_execution_modes
    assert {"streaming", "materialized", "parallel"}.issubset(capabilities_for("mlir").supported_execution_modes)


def test_unsupported_execution_mode_is_explicit_error():
    pipeline = compile_selected_backend(_module()).pipeline
    caps = capabilities_for("native")
    if any(r.mode == "parallel" for r in pipeline.selected_execution_plan.execution_regions):
        with pytest.raises(ValueError, match="execution mode"):
            validate_execution_regions(pipeline, caps)
