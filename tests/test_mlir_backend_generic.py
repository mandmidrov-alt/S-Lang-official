import sys
from pathlib import Path
sys.path.insert(0, '.')
from slang.core import parse, validate
from slang.mlir_backend import lower_execution_ir_to_mlir, format_backend_lowering


def test_data_operations_lower_to_slang_mlir():
    p = parse(Path('examples/data_generic.sl').read_text())
    validate(p)
    text = lower_execution_ir_to_mlir(p.ast)
    assert 'func.call @slang_filter' in text
    assert 'func.call @slang_sort' in text
    assert 'cardinality = 3 : i64' in text
    assert 'complexity = "nlogn"' in text


def test_goal_operations_lower_to_slang_mlir():
    p = parse(Path('examples/goal_ir.sl').read_text())
    validate(p)
    text = lower_execution_ir_to_mlir(p.ast)
    assert 'func.call @slang_choose' in text
    assert 'func.call @slang_find_path' in text
    assert 'func.call @slang_satisfy' in text


def test_lowering_is_explicitly_non_executable_for_generic_ops():
    p = parse(Path('examples/data_generic.sl').read_text())
    validate(p)
    report = format_backend_lowering(p.ast)
    assert 'representation = slang-runtime-abi-mlir' in report
    assert 'runtime_abi = explicit-i64-handles' in report
