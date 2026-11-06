"""Contract tests for the opaque native List<Number> runtime ABI."""
import ctypes
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_native_number_list_runtime_abi(tmp_path):
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if not compiler:
        pytest.skip("a C compiler is required for the runtime ABI test")
    source = ROOT / "slang" / "slang_runtime.c"
    library = tmp_path / ("slang_runtime.dll" if __import__("os").name == "nt" else "libslang_runtime.so")
    command = [compiler, "-shared", "-fPIC", str(source), "-o", str(library), "-lm"]
    subprocess.run(command, check=True, capture_output=True, text=True)
    runtime = ctypes.CDLL(str(library))

    runtime.slang_number_list_new.argtypes = [ctypes.c_size_t]
    runtime.slang_number_list_new.restype = ctypes.c_void_p
    runtime.slang_number_list_set.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_double]
    runtime.slang_number_list_set.restype = ctypes.c_int
    runtime.slang_number_list_append.argtypes = [ctypes.c_void_p, ctypes.c_double]
    runtime.slang_number_list_append.restype = ctypes.c_int
    runtime.slang_number_list_count.argtypes = [ctypes.c_void_p]
    runtime.slang_number_list_count.restype = ctypes.c_long
    runtime.slang_number_list_item.argtypes = [ctypes.c_void_p, ctypes.c_long]
    runtime.slang_number_list_item.restype = ctypes.c_double
    runtime.slang_number_list_free.argtypes = [ctypes.c_void_p]

    values = runtime.slang_number_list_new(3)
    assert values
    try:
        assert runtime.slang_number_list_count(values) == 3
        assert runtime.slang_number_list_set(values, 0, 1.25) == 1
        assert runtime.slang_number_list_set(values, 1, -2.5) == 1
        assert runtime.slang_number_list_set(values, 2, 4.0) == 1
        assert [runtime.slang_number_list_item(values, i) for i in range(3)] == [1.25, -2.5, 4.0]
        assert runtime.slang_number_list_set(values, 3, 9.0) == 0
        assert runtime.slang_number_list_item(values, 3) == 0.0
        assert runtime.slang_number_list_append(values, 8.5) == 1
        assert runtime.slang_number_list_count(values) == 4
        assert runtime.slang_number_list_item(values, 3) == 8.5
    finally:
        runtime.slang_number_list_free(values)

    empty = runtime.slang_number_list_new(0)
    assert empty
    try:
        assert runtime.slang_number_list_count(empty) == 0
        assert runtime.slang_number_list_item(empty, 0) == 0.0
    finally:
        runtime.slang_number_list_free(empty)
