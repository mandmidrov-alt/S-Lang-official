import ctypes, subprocess
from pathlib import Path


def bits(v):
    import struct
    return struct.unpack('q', struct.pack('d', float(v)))[0]


def test_runtime_multi_field_expression_map_is_single_atomic_program(tmp_path):
    so = tmp_path / 'libslang_runtime.so'
    subprocess.run(['cc','-shared','-fPIC','runtime/slang_runtime.c','-o',str(so),'-lm'], check=True)
    lib = ctypes.CDLL(str(so))
    lib.slang_record_f64_new_flat.argtypes=[ctypes.POINTER(ctypes.c_double),ctypes.c_long,ctypes.c_long]; lib.slang_record_f64_new_flat.restype=ctypes.c_int64
    lib.slang_record_f64_map_fields_expr.argtypes=[ctypes.c_int64,ctypes.POINTER(ctypes.c_int64),ctypes.c_long]; lib.slang_record_f64_map_fields_expr.restype=ctypes.c_int64
    lib.slang_record_f64_get.argtypes=[ctypes.c_int64,ctypes.c_long,ctypes.c_long]; lib.slang_record_f64_get.restype=ctypes.c_double
    lib.slang_record_f64_free.argtypes=[ctypes.c_int64]
    data=(ctypes.c_double*6)(20,50,30,70,40,95)
    src=lib.slang_record_f64_new_flat(data,2,3)
    # field 0 := age + 1; field 1 := score - age
    prog=(ctypes.c_int64*40)(
        1,0,0,0,0, 2,0,0,0,bits(1), 3,0,0,0,0, 20,0,0,0,0,
        1,1,0,0,0, 1,0,0,0,0, 4,0,0,0,0, 20,1,0,0,0,
    )
    out=lib.slang_record_f64_map_fields_expr(src, prog, 8)
    assert out
    assert [lib.slang_record_f64_get(out,0,i) for i in range(3)] == [21,31,41]
    assert [lib.slang_record_f64_get(out,1,i) for i in range(3)] == [30,40,55]
    lib.slang_record_f64_free(out); lib.slang_record_f64_free(src)
