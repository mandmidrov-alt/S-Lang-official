import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from slang.core import parse
from slang.mlir_backend import lower_execution_ir_to_mlir

def test_mlir_numeric_power_uses_concrete_runtime_opcode():
    module = parse("""data numbers:
    a value 2
    b value 3

mapped = numbers map item ^ 2
show mapped
""").ast
    text = lower_execution_ir_to_mlir(module)
    assert "slang_collection_f64_map" in text
    assert ", 2.000000" in text or ", 2" in text
    assert ", 4)" in text or ", 4 : i32)" in text
