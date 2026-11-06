import ctypes, subprocess
from pathlib import Path


def build(tmp_path):
    so=tmp_path/'libslang_runtime.so'
    subprocess.run(['cc','-shared','-fPIC','runtime/slang_runtime.c','-o',str(so),'-lm'],check=True)
    return ctypes.CDLL(str(so))


def test_runtime_boolean_expression_supports_or_and_not(tmp_path):
    lib=build(tmp_path)
    lib.slang_record_f64_new_flat.argtypes=[ctypes.POINTER(ctypes.c_double),ctypes.c_long,ctypes.c_long]; lib.slang_record_f64_new_flat.restype=ctypes.c_int64
    lib.slang_record_f64_filter_expr.argtypes=[ctypes.c_int64,ctypes.POINTER(ctypes.c_int64),ctypes.c_long]; lib.slang_record_f64_filter_expr.restype=ctypes.c_int64
    lib.slang_record_f64_get.argtypes=[ctypes.c_int64,ctypes.c_long,ctypes.c_long]; lib.slang_record_f64_get.restype=ctypes.c_double
    lib.slang_record_f64_count.argtypes=[ctypes.c_int64]; lib.slang_record_f64_count.restype=ctypes.c_long
    lib.slang_record_f64_free.argtypes=[ctypes.c_int64]
    data=(ctypes.c_double*6)(20,50,30,70,40,95)
    src=lib.slang_record_f64_new_flat(data,2,3)
    # not(age < 30) or score > age*2
    # leaf age<30, NOT, leaf score>age*2, OR
    prog=(ctypes.c_int64*25)(1,0,-1,2,struct_bits(30),5,0,0,0,0,2,1,0,0,struct_bits(2.0),4,0,0,0,0)
    out=lib.slang_record_f64_filter_expr(src,prog,4)
    assert lib.slang_record_f64_count(out)==3
    assert [lib.slang_record_f64_get(out,0,i) for i in range(3)]==[20,30,40]
    lib.slang_record_f64_free(out); lib.slang_record_f64_free(src)


def struct_bits(v):
    import struct
    return struct.unpack('q',struct.pack('d',float(v)))[0]


def test_runtime_numeric_expression_supports_conditional_map(tmp_path):
    lib=build(tmp_path)
    lib.slang_record_f64_new_flat.argtypes=[ctypes.POINTER(ctypes.c_double),ctypes.c_long,ctypes.c_long]; lib.slang_record_f64_new_flat.restype=ctypes.c_int64
    lib.slang_record_f64_map_field_expr.argtypes=[ctypes.c_int64,ctypes.c_long,ctypes.POINTER(ctypes.c_int64),ctypes.c_long]; lib.slang_record_f64_map_field_expr.restype=ctypes.c_int64
    lib.slang_record_f64_get.argtypes=[ctypes.c_int64,ctypes.c_long,ctypes.c_long]; lib.slang_record_f64_get.restype=ctypes.c_double
    lib.slang_record_f64_free.argtypes=[ctypes.c_int64]
    data=(ctypes.c_double*4)(20,50,30,70)
    src=lib.slang_record_f64_new_flat(data,2,2)
    # if score > 60 then score-age else score+age
    prog=(ctypes.c_int64*50)(
        1,1,0,0,0, 2,0,0,0,struct_bits(60), 10,0,0,0,0,
        1,1,0,0,0, 1,0,0,0,0, 4,0,0,0,0,
        1,1,0,0,0, 1,0,0,0,0, 3,0,0,0,0,
        8,0,0,0,0,
    )
    out=lib.slang_record_f64_map_field_expr(src,1,prog,10)
    assert [lib.slang_record_f64_get(out,1,i) for i in range(2)] == [70.0,40.0]
    assert [lib.slang_record_f64_get(out,0,i) for i in range(2)] == [20.0,30.0]
    lib.slang_record_f64_free(out); lib.slang_record_f64_free(src)
