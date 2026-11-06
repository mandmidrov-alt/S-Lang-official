"""Regression tests for consistent top-level and function block conditionals."""

import pytest

from slang.core import ParseError, parse, run, validate, show_expr_value


def _outputs(source):
    program = parse(source)
    validate(program)
    run(program)
    return [show_expr_value(program, expression) for expression in program.show_exprs]


def test_top_level_if_else_executes_selected_branch():
    assert _outputs('''let system_load = 68
if system_load >= 90:
    show "Critical"
else:
    if system_load >= 70:
        show "High"
    else:
        show "Normal"
''') == ["Normal"]


def test_top_level_if_keeps_source_order_of_shows():
    assert _outputs('''let enabled = true
show "before"
if enabled:
    show "inside"
else:
    show "not selected"
show "after"
''') == ["before", "inside", "after"]


def test_top_level_if_supports_scoped_let_and_show():
    assert _outputs('''let enabled = true
if enabled:
    let message = "branch passed"
    show message
else:
    let message = "branch failed"
    show message
show enabled
''') == ["branch passed", "True"]


def test_top_level_if_without_else_can_emit_nothing():
    assert _outputs('''let enabled = false
if enabled:
    show "selected"
''') == []


def test_top_level_if_condition_must_be_boolean():
    program = parse('''let count = 3
if count:
    show "invalid"
''')
    with pytest.raises(TypeError, match="if condition must be Boolean"):
        validate(program)


def test_top_level_if_does_not_allow_return():
    with pytest.raises(ParseError, match="return is only allowed"):
        parse('''let enabled = true
if enabled:
    return 3
''')


def test_top_level_if_branch_variable_does_not_escape_scope():
    program = parse('''let enabled = true
if enabled:
    let hidden = 3
show hidden
''')
    with pytest.raises(TypeError, match="unknown value|unknown name"):
        validate(program)


def test_function_block_if_still_works():
    assert _outputs('''function classify(score: Number) -> Text:
    if score >= 90:
        return "excellent"
    else:
        return "other"
let result = classify(92)
show result
''') == ["excellent"]


def test_native_backend_rejects_top_level_block_if_instead_of_silently_ignoring_it():
    from slang.core import llvm_ir

    program = parse('''let enabled = true
if enabled:
    show "selected"
''')
    with pytest.raises(ValueError, match="native LLVM lowering does not yet support top-level block if"):
        llvm_ir(program)


def test_nested_block_cannot_redeclare_parent_block_local():
    program = parse('''let enabled = true
if enabled:
    let local_value = 1
    if enabled:
        let local_value = 2
        show local_value
''')
    with pytest.raises(TypeError, match="duplicate local variable 'local_value'"):
        validate(program)
