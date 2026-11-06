import subprocess
import sys
from pathlib import Path

from slang.backend import native_capabilities, capabilities_for
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.core import parse

ROOT = Path(__file__).resolve().parents[1]


def test_native_capabilities_expose_selected_strategy_contract():
    caps = native_capabilities()
    assert "fused-filter-map-reduce" in caps.supported_strategies
    assert caps.supports("sequential-reduce")
    assert not caps.supports("parallel-stable-sort")


def test_backend_capabilities_cli_compares_backends():
    p = subprocess.run(
        [sys.executable, "-m", "slang.cli", "backend-capabilities", "examples/fused_reduce.sl"],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert p.returncode == 0, p.stderr
    assert p.stdout.count("backend.capabilities {") == 2
    assert "backend = native-llvm" in p.stdout
    assert "backend = mlir-llvm" in p.stdout
    assert "unsupported_selected = none" in p.stdout


def test_semantic_pipeline_remains_backend_independent():
    pipeline = compile_semantic_pipeline(parse(Path(ROOT / "examples/fused_reduce.sl").read_text()).ast)
    assert any(c.strategy == "fused-filter-map-reduce" for c in pipeline.strategies)
