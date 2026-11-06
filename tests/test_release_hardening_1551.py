import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from slang.core import parse, validate
from slang.execution_ir import build_execution_ir
from slang.mlir_backend import lower_execution_ir_to_mlir


def test_external_function_contracts_do_not_form_execution_ir_cycles():
    p = parse("""record Flag:
    active: Boolean
let flags = [Flag(false), Flag(true)]
result = flags reduce false with acc or item.active
show result
""")
    validate(p)
    ir = build_execution_ir(p.ast)
    order = ir.topological_order()
    assert order == ("flags#1", "result#1", "@show:1#1")


def test_record_field_sort_uses_generic_mlir_abi_fallback():
    p = parse(Path("examples/data_generic.sl").read_text())
    validate(p)
    text = lower_execution_ir_to_mlir(p.ast)
    assert "func.call @slang_filter" in text
    assert "func.call @slang_sort" in text
    assert "func.call @slang_collection_f64_sort" not in text
