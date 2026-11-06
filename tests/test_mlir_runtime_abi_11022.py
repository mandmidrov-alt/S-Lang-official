import sys
from pathlib import Path
sys.path.insert(0, '.')
from slang.core import parse, validate
from slang.mlir_backend import lower_execution_ir_to_mlir


def test_generic_tokens_lower_to_runtime_calls():
    p = parse(Path('examples/data_generic.sl').read_text())
    validate(p)
    text = lower_execution_ir_to_mlir(p.ast)
    assert 'func.call @slang_filter' in text
    assert 'func.call @slang_sort' in text
    assert 'slang.filter {' not in text
    assert 'slang.sort {' not in text
    assert 'func.func private @slang_filter' in text
    assert 'func.func private @slang_sort' in text


def test_goal_tokens_lower_to_runtime_calls():
    p = parse(Path('examples/goal_ir.sl').read_text())
    validate(p)
    text = lower_execution_ir_to_mlir(p.ast)
    assert 'func.call @slang_choose' in text
    assert 'func.call @slang_find_path' in text
    assert 'func.call @slang_satisfy' in text


def test_runtime_abi_is_dependency_driven():
    p = parse(Path('examples/data_generic.sl').read_text())
    validate(p)
    text = lower_execution_ir_to_mlir(p.ast)
    # The runtime boundary is explicit even when a node has no preceding SSA value.
    assert 'func.call @slang_filter(%zero)' in text
