from slang.backend import format_backend_selection, select_backend
from slang.core import parse_file, validate


def load(name):
    p = parse_file(name)
    validate(p)
    return p.ast


def test_native_selected_for_fused_numeric_program():
    selection = select_backend(load("examples/fused_reduce.sl"))
    assert selection.selected == "native-llvm"
    assert selection.deterministic
    assert all(c.compatible is False or c.toolchain_ready for c in selection.candidates)


def test_satisfy_rejects_native_capability_contract():
    selection = select_backend(load("examples/satisfy.sl"))
    native = next(c for c in selection.candidates if c.backend == "native-llvm")
    assert not native.compatible
    assert any("unsupported-operations" in r or "unsupported-domains" in r for r in native.reasons)


def test_selection_format_is_explicit():
    text = format_backend_selection(select_backend(load("examples/fused_reduce.sl")))
    assert "backend.selection {" in text
    assert "selected = native-llvm" in text
    assert "deterministic = yes" in text
