import ctypes, subprocess
from pathlib import Path


def bits(v):
    import struct
    return struct.unpack('q', struct.pack('d', float(v)))[0]


def test_runtime_mixed_projection_selects_and_reorders_fields(tmp_path):
    so = tmp_path / 'libslang_runtime.so'
    subprocess.run(['cc','-shared','-fPIC','runtime/slang_runtime.c','-o',str(so),'-lm'], check=True)
    lib = ctypes.CDLL(str(so))
    I64=ctypes.c_int64
    lib.slang_record_mixed_new_flat.argtypes=[ctypes.POINTER(I64),ctypes.POINTER(I64),ctypes.POINTER(I64),ctypes.c_long,ctypes.c_long]
    lib.slang_record_mixed_new_flat.restype=I64
    lib.slang_record_mixed_project_fields.argtypes=[I64,ctypes.POINTER(I64),ctypes.POINTER(I64),ctypes.c_long]
    lib.slang_record_mixed_project_fields.restype=I64
    lib.slang_record_mixed_get_number.argtypes=[I64,ctypes.c_long,ctypes.c_long]; lib.slang_record_mixed_get_number.restype=ctypes.c_double
    lib.slang_record_mixed_get_bool.argtypes=[I64,ctypes.c_long,ctypes.c_long]; lib.slang_record_mixed_get_bool.restype=ctypes.c_int
    lib.slang_record_mixed_get_text.argtypes=[I64,ctypes.c_long,ctypes.c_long]; lib.slang_record_mixed_get_text.restype=ctypes.c_char_p
    lib.slang_record_mixed_free.argtypes=[I64]

    # Person(name: Text, age: Number, active: Boolean, score: Number)
    types=(I64*4)(2,0,1,0)
    values=(I64*8)(0,bits(20),1,bits(90),0,bits(30),0,bits(70))
    texts=(I64*8)(ctypes.cast(ctypes.c_char_p(b'Ada'),ctypes.c_void_p).value,0,0,0,ctypes.cast(ctypes.c_char_p(b'Bob'),ctypes.c_void_p).value,0,0,0)
    src=lib.slang_record_mixed_new_flat(types,values,texts,4,2)
    assert src
    # Summary(label: Text, score: Number, active: Boolean): source fields 0,3,2
    source=(I64*3)(0,3,2)
    target=(I64*3)(2,0,1)
    out=lib.slang_record_mixed_project_fields(src,source,target,3)
    assert out
    assert lib.slang_record_mixed_get_text(out,0,0)==b'Ada'
    assert lib.slang_record_mixed_get_number(out,1,0)==90.0
    assert lib.slang_record_mixed_get_bool(out,2,0)==1
    assert lib.slang_record_mixed_get_text(out,0,1)==b'Bob'
    assert lib.slang_record_mixed_get_number(out,1,1)==70.0
    assert lib.slang_record_mixed_get_bool(out,2,1)==0
    lib.slang_record_mixed_free(out); lib.slang_record_mixed_free(src)
