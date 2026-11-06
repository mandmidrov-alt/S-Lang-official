import ctypes
import subprocess


def test_runtime_numeric_record_mask_preserves_selected_columns(tmp_path):
    so = tmp_path / 'libslang_runtime.so'
    subprocess.run(['cc', '-shared', '-fPIC', 'runtime/slang_runtime.c', '-o', str(so), '-lm'], check=True)
    lib = ctypes.CDLL(str(so))
    I64 = ctypes.c_int64
    lib.slang_record_f64_new_flat.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_long, ctypes.c_long]
    lib.slang_record_f64_new_flat.restype = I64
    lib.slang_record_f64_mask_fields.argtypes = [I64, ctypes.POINTER(I64), ctypes.c_long]
    lib.slang_record_f64_mask_fields.restype = I64
    lib.slang_record_f64_get.argtypes = [I64, ctypes.c_long, ctypes.c_long]
    lib.slang_record_f64_get.restype = ctypes.c_double
    lib.slang_record_f64_free.argtypes = [I64]

    values = (ctypes.c_double * 4)(2.0, 10.0, 3.0, 20.0)
    src = lib.slang_record_f64_new_flat(values, 2, 2)
    selected = (I64 * 1)(0)
    out = lib.slang_record_f64_mask_fields(src, selected, 1)
    assert out
    assert lib.slang_record_f64_get(out, 0, 0) == 2.0
    assert lib.slang_record_f64_get(out, 1, 0) == 0.0
    assert lib.slang_record_f64_get(out, 0, 1) == 3.0
    assert lib.slang_record_f64_get(out, 1, 1) == 0.0
    lib.slang_record_f64_free(out)
    lib.slang_record_f64_free(src)
