"""Executable Native JIT contract tests for List<Number> terminal operations."""
import shutil
import subprocess
from pathlib import Path

import pytest

from slang.core import parse, validate, _native_function_llvm_ir

ROOT = Path(__file__).resolve().parents[1]
COMPILER = shutil.which("clang") or shutil.which("cc") or shutil.which("gcc")


def _run_native_terminal(tmp_path, operation, return_type, values, *, pipeline=None):
    if not COMPILER:
        pytest.skip("a C compiler is required for native terminal execution tests")
    program = parse(
        f"function calculate(values: List<Number>) -> {return_type}:\n"
        f"    let result = values |> {pipeline or operation}\n"
        "    return result\n"
    )
    validate(program)
    function_ir, signatures = _native_function_llvm_ir(program)
    assert signatures["calculate"] == (("ptr",), "i1" if return_type == "Boolean" else "double")
    ir_path = tmp_path / f"{operation}.ll"
    ir_path.write_text("\n".join(function_ir) + "\n", encoding="utf-8")

    bool_result = return_type == "Boolean"
    harness = tmp_path / "harness.c"
    result_decl = "extern _Bool calculate(SlangNumberList *);" if bool_result else "extern double calculate(SlangNumberList *);"
    result_print = 'printf("%s\\n", calculate(values) ? "true" : "false");' if bool_result else 'printf("%.12g\\n", calculate(values));'
    harness.write_text(
        "#include <stdio.h>\n#include <stdint.h>\n"
        "typedef struct SlangNumberList SlangNumberList;\n"
        "SlangNumberList *slang_number_list_new(size_t);\n"
        "int slang_number_list_set(SlangNumberList *, size_t, double);\n"
        "void slang_number_list_free(SlangNumberList *);\n"
        f"{result_decl}\n"
        "int main(void) {\n"
        f"  double input[] = {{{', '.join(str(float(v)) for v in values)}}};\n"
        f"  SlangNumberList *values = slang_number_list_new({len(values)});\n"
        f"  for (size_t i = 0; i < {len(values)}; ++i) slang_number_list_set(values, i, input[i]);\n"
        f"  {result_print}\n"
        "  slang_number_list_free(values); return 0;\n}\n",
        encoding="utf-8",
    )
    executable = tmp_path / "native-terminal"
    built = subprocess.run(
        [COMPILER, str(ir_path), str(harness), str(ROOT / "slang" / "slang_runtime.c"), *( ["-lm"] if __import__("os").name != "nt" else [] ), "-o", str(executable)],
        capture_output=True, text=True,
    )
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([str(executable)], capture_output=True, text=True)
    assert ran.returncode == 0, ran.stderr
    return ran.stdout.strip()


@pytest.mark.parametrize(
    ("operation", "return_type", "values", "expected"),
    [
        ("min", "Number", [3, 1, 4, 2], "1"),
        ("max", "Number", [3, 1, 4, 2], "4"),
        ("average", "Number", [3, 1, 4, 2], "2.5"),
        ("avg", "Number", [3, 1, 4, 2], "2.5"),
        ("any", "Boolean", [0, 0, 2, 0], "true"),
        ("any", "Boolean", [0, 0, 0], "false"),
        ("all", "Boolean", [1, 2, 3], "true"),
        ("all", "Boolean", [1, 0, 3], "false"),
    ],
)
def test_native_number_list_terminal_executes(tmp_path, operation, return_type, values, expected):
    assert _run_native_terminal(tmp_path, operation, return_type, values) == expected


def test_native_number_list_filter_map_then_terminal_executes(tmp_path):
    assert _run_native_terminal(
        tmp_path, "where_map_average", "Number", [3, 1, 4, 2],
        pipeline="where item >= 2 |> map item * 3 |> average",
    ) == "9"


def test_native_number_list_sort_then_reduce_executes(tmp_path):
    assert _run_native_terminal(
        tmp_path, "sort_reduce", "Number", [4, 1, 3, 2],
        pipeline="sort by item asc |> reduce 0 with acc + item",
    ) == "10"


def test_native_number_list_sort_descending_then_reduce_executes(tmp_path):
    assert _run_native_terminal(
        tmp_path, "sort_reduce_desc", "Number", [2, 4, 3],
        pipeline="sort by item desc |> reduce 1 with acc * item",
    ) == "24"


def test_native_number_list_reduce_preserves_left_to_right_order(tmp_path):
    assert _run_native_terminal(
        tmp_path, "reduce_order", "Number", [2, 3, 4],
        pipeline="reduce 20 with acc - item",
    ) == "11"


def test_native_number_list_numeric_terminal_projections_execute(tmp_path):
    assert _run_native_terminal(
        tmp_path, "min_projection", "Number", [1, 4, 2],
        pipeline="min item * 2 - 3",
    ) == "-1"
    assert _run_native_terminal(
        tmp_path, "max_projection", "Number", [1, 4, 2],
        pipeline="max item * 2 - 3",
    ) == "5"
    assert _run_native_terminal(
        tmp_path, "average_projection", "Number", [1, 4, 2],
        pipeline="average item * 2 - 3",
    ) == "1.66666666667"
    assert _run_native_terminal(
        tmp_path, "sum_projection", "Number", [1, 4, 2],
        pipeline="sum item * 2 - 3",
    ) == "5"


def test_native_number_list_sort_projection_keeps_original_values(tmp_path):
    assert _run_native_terminal(
        tmp_path, "sort_projection", "Number", [1, 4, 2],
        pipeline="sort by (item - 3) * (item - 3) asc |> reduce 0 with acc * 10 + item",
    ) == "421"


def test_native_number_list_boolean_terminal_projections_execute(tmp_path):
    assert _run_native_terminal(
        tmp_path, "any_projection", "Boolean", [1, 4, 2],
        pipeline="any item > 3",
    ) == "true"
    assert _run_native_terminal(
        tmp_path, "all_projection", "Boolean", [1, 4, 2],
        pipeline="all item > 0",
    ) == "true"
    assert _run_native_terminal(
        tmp_path, "all_projection_false", "Boolean", [1, 4, 2],
        pipeline="all item > 2",
    ) == "false"


def test_native_number_list_map_then_where_then_terminal_executes(tmp_path):
    assert _run_native_terminal(
        tmp_path, "map_where_sum", "Number", [1, 2, 3, 4],
        pipeline="map item * 2 |> where item >= 6 |> sum",
    ) == "14"


def test_native_number_list_repeated_stable_sorts_then_reduce_execute(tmp_path):
    assert _run_native_terminal(
        tmp_path, "repeated_sort_reduce", "Number", [3, 1, 2],
        pipeline="sort by item asc |> sort by item desc |> reduce 0 with acc * 10 + item",
    ) == "321"
