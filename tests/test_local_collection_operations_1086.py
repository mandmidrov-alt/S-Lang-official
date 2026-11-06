from slang.core import parse, validate, run, show_expr_value


def outputs(source):
    program = parse(source)
    validate(program)
    run(program)
    return [show_expr_value(program, expr) for expr in program.show_exprs]


def test_collection_where_map_aggregate_inside_function():
    assert outputs('''function calculate(values: List<Number>, threshold: Number) -> Number:
    let selected = values where item >= threshold
    let doubled = selected map item * 2
    let total = doubled sum
    return total
let values = [1, 2, 3, 4]
let answer = calculate(values, 3)
show answer
''') == ["14"]


def test_collection_pipeline_inside_function():
    assert outputs('''function calculate(values: List<Number>) -> Number:
    let result = values |> where item >= 2 |> map item * 3 |> sum
    return result
let values = [1, 2, 3, 4]
let answer = calculate(values)
show answer
''') == ["27"]


def test_collection_inside_top_level_if_block():
    assert outputs('''let values = [4, 1, 3, 2]
let enabled = true
if enabled:
    let sorted = values sort by item asc
    let total = sorted sum
    show total
else:
    show 0
''') == ["10"]


def test_local_reduce_and_sort_descending():
    assert outputs('''function calculate(values: List<Number>) -> Number:
    let sorted = values sort by item desc
    let total = sorted reduce 0 with acc + item
    return total
let values = [4, 1, 3, 2]
let answer = calculate(values)
show answer
''') == ["10"]



def test_local_collection_uses_outer_lexical_variable():
    assert outputs('''function calculate(values: List<Number>, threshold: Number) -> Number:
    let selected = values where item >= threshold
    let total = selected sum
    return total
let values = [1, 3, 7, 9]
let answer = calculate(values, 7)
show answer
''') == ["16"]


def test_local_sort_returns_expected_order():
    assert outputs('''function ordered(values: List<Number>) -> List<Number>:
    let sorted = values sort by item desc
    return sorted
let values = [4, 1, 3, 2]
let answer = ordered(values)
show answer
''') == ["[4, 3, 2, 1]"]


def test_native_jit_lowers_sum_for_number_list_parameter():
    from slang.core import _native_function_llvm_ir
    import llvmlite.binding as llvm

    program = parse('''function calculate(values: List<Number>) -> Number:
    let total = values sum
    return total
''')
    validate(program)
    ir, signatures = _native_function_llvm_ir(program)
    rendered = "\n".join(ir)
    assert signatures["calculate"] == (("ptr",), "double")
    assert "call i64 @slang_number_list_count" in rendered
    assert "call double @slang_number_list_item" in rendered
    assert "fadd double" in rendered
    module = llvm.parse_assembly(rendered)
    module.verify()


def test_native_jit_lowers_count_for_number_list_parameter():
    from slang.core import _native_function_llvm_ir
    import llvmlite.binding as llvm

    program = parse('''function calculate(values: List<Number>) -> Number:
    let total = values count
    return total
''')
    validate(program)
    ir, _ = _native_function_llvm_ir(program)
    rendered = "\n".join(ir)
    assert "call i64 @slang_number_list_count" in rendered
    assert "uitofp i64" in rendered
    llvm.parse_assembly(rendered).verify()


def test_local_where_rejects_non_boolean_predicate():
    import pytest

    program = parse('''function calculate(values: List<Number>) -> Number:
    let selected = values where item + 1
    let total = selected sum
    return total
''')
    with pytest.raises(TypeError, match="where condition must be Boolean"):
        validate(program)


def test_native_function_abi_accepts_opaque_number_list_parameter():
    from slang.core import _native_function_llvm_ir

    program = parse('''function consume(values: List<Number>) -> Number:
    return 1
function forward(values: List<Number>) -> Number:
    return consume(values)
''')
    validate(program)
    ir, signatures = _native_function_llvm_ir(program)
    assert signatures["consume"] == (("ptr",), "double")
    assert signatures["forward"] == (("ptr",), "double")
    rendered = "\\n".join(ir)
    assert "define double @consume(ptr %values)" in rendered
    assert "call double @consume(ptr %values)" in rendered


def test_native_function_abi_rejects_unsupported_list_element_type():
    import pytest
    from slang.core import _native_function_llvm_ir

    program = parse('''function consume(values: List<Text>) -> Number:
    return 1
''')
    validate(program)
    with pytest.raises(ValueError, match="supports List<Number> parameters only"):
        _native_function_llvm_ir(program)


def test_native_jit_lowers_number_list_where_and_map_pipeline():
    from slang.core import _native_function_llvm_ir
    import llvmlite.binding as llvm

    program = parse('''function calculate(values: List<Number>, threshold: Number) -> Number:
    let total = values |> where item >= threshold |> map item * 2 |> sum
    return total
''')
    validate(program)
    ir, _ = _native_function_llvm_ir(program)
    rendered = "\n".join(ir)
    assert "@slang_number_list_append" in rendered
    assert "@slang_number_list_new" in rendered
    assert "@slang_number_list_set" in rendered
    assert "@slang_number_list_free" in rendered
    assert "fcmp oge double" in rendered
    assert "fmul double" in rendered
    llvm.parse_assembly(rendered).verify()


def test_native_jit_lowers_map_only_for_number_list():
    from slang.core import _native_function_llvm_ir
    import llvmlite.binding as llvm

    program = parse('''function calculate(values: List<Number>) -> Number:
    let total = values |> map item * 3 |> sum
    return total
''')
    validate(program)
    ir, _ = _native_function_llvm_ir(program)
    llvm.parse_assembly("\n".join(ir)).verify()
