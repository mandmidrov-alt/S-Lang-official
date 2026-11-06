import ctypes
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _lib(tmp_path):
    out = tmp_path / 'libslang_runtime.so'
    subprocess.run(['gcc', '-shared', '-fPIC', '-O2', 'runtime/slang_runtime.c', '-o', str(out)], cwd=ROOT, check=True)
    return ctypes.CDLL(str(out))


def test_numeric_collection_filter_map_reduce_aggregate(tmp_path):
    lib = _lib(tmp_path)
    lib.slang_collection_f64_new.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_long]
    lib.slang_collection_f64_new.restype = ctypes.c_int64
    lib.slang_collection_f64_filter.argtypes = [ctypes.c_int64, ctypes.c_double, ctypes.c_int]
    lib.slang_collection_f64_filter.restype = ctypes.c_int64
    lib.slang_collection_f64_map.argtypes = [ctypes.c_int64, ctypes.c_double, ctypes.c_int]
    lib.slang_collection_f64_map.restype = ctypes.c_int64
    lib.slang_collection_f64_reduce.argtypes = [ctypes.c_int64, ctypes.c_double, ctypes.c_int]
    lib.slang_collection_f64_reduce.restype = ctypes.c_double
    lib.slang_collection_f64_aggregate.argtypes = [ctypes.c_int64, ctypes.c_int]
    lib.slang_collection_f64_aggregate.restype = ctypes.c_double
    lib.slang_collection_f64_count.argtypes = [ctypes.c_int64]
    lib.slang_collection_f64_count.restype = ctypes.c_long
    lib.slang_collection_f64_get.argtypes = [ctypes.c_int64, ctypes.c_long]
    lib.slang_collection_f64_get.restype = ctypes.c_double
    lib.slang_collection_free.argtypes = [ctypes.c_int64]

    values = (ctypes.c_double * 5)(1, 2, 3, 4, 5)
    source = lib.slang_collection_f64_new(values, 5)
    filtered = lib.slang_collection_f64_filter(source, 2.0, 0)  # > 2
    mapped = lib.slang_collection_f64_map(filtered, 10.0, 0)    # * 10
    powered = lib.slang_collection_f64_map(source, 2.0, 4)       # ^ 2
    assert lib.slang_collection_f64_count(powered) == 5
    assert [lib.slang_collection_f64_get(powered, i) for i in range(5)] == [1.0, 4.0, 9.0, 16.0, 25.0]
    assert lib.slang_collection_f64_count(mapped) == 3
    assert [lib.slang_collection_f64_get(mapped, i) for i in range(3)] == [30.0, 40.0, 50.0]
    assert lib.slang_collection_f64_reduce(mapped, 0.0, 0) == 120.0
    assert lib.slang_collection_f64_aggregate(mapped, 1) == 30.0
    assert lib.slang_collection_f64_aggregate(mapped, 2) == 50.0
    assert lib.slang_collection_f64_aggregate(mapped, 3) == 3.0
    lib.slang_collection_free(powered)
    lib.slang_collection_free(mapped)
    lib.slang_collection_free(filtered)
    lib.slang_collection_free(source)


def test_numeric_collection_sort_is_non_mutating(tmp_path):
    lib = _lib(tmp_path)
    lib.slang_collection_f64_new.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_long]
    lib.slang_collection_f64_new.restype = ctypes.c_int64
    lib.slang_collection_f64_sort.argtypes = [ctypes.c_int64]
    lib.slang_collection_f64_sort.restype = ctypes.c_int64
    lib.slang_collection_f64_get.argtypes = [ctypes.c_int64, ctypes.c_long]
    lib.slang_collection_f64_get.restype = ctypes.c_double
    lib.slang_collection_free.argtypes = [ctypes.c_int64]
    values = (ctypes.c_double * 4)(4, 1, 3, 2)
    source = lib.slang_collection_f64_new(values, 4)
    sorted_handle = lib.slang_collection_f64_sort(source)
    assert [lib.slang_collection_f64_get(sorted_handle, i) for i in range(4)] == [1, 2, 3, 4]
    assert [lib.slang_collection_f64_get(source, i) for i in range(4)] == [4, 1, 3, 2]
    lib.slang_collection_free(sorted_handle)
    lib.slang_collection_free(source)
