from pathlib import Path
from slang.core import parse, validate
from slang.mlir_backend import lower_execution_ir_to_mlir
from slang.backend import compile_selected_backend


def _module():
    p = parse(Path("examples/data_generic.sl").read_text())
    validate(p)
    return p.ast


def test_mlir_lowering_consumes_selected_execution_regions():
    module = _module()
    pipeline = compile_selected_backend(module).pipeline
    assert pipeline.selected_execution_plan.execution_regions
    text = lower_execution_ir_to_mlir(module, pipeline=pipeline)
    assert "slang.execution_region" in text
    assert "execution_region =" in text
    assert "execution_mode =" in text


def test_backend_selection_and_lowering_are_deterministic():
    module = _module()
    a = compile_selected_backend(module)
    b = compile_selected_backend(module)
    assert a.pipeline.selected_execution_plan.execution_regions == b.pipeline.selected_execution_plan.execution_regions
    assert lower_execution_ir_to_mlir(module, pipeline=a.pipeline) == lower_execution_ir_to_mlir(module, pipeline=b.pipeline)
