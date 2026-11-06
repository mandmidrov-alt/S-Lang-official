import ctypes, subprocess
from pathlib import Path


def bits(v):
    import struct
    return struct.unpack('q', struct.pack('d', float(v)))[0]


def test_runtime_mixed_record_filter_and_atomic_map(tmp_path):
    so = tmp_path / 'libslang_runtime.so'
    subprocess.run(['cc','-shared','-fPIC','runtime/slang_runtime.c','-o',str(so),'-lm'], check=True)
    lib=ctypes.CDLL(str(so))
    i64=ctypes.c_int64
    lib.slang_record_mixed_new_flat.argtypes=[ctypes.POINTER(i64),ctypes.POINTER(i64),ctypes.POINTER(i64),ctypes.c_long,ctypes.c_long]; lib.slang_record_mixed_new_flat.restype=i64
    lib.slang_record_mixed_filter_expr.argtypes=[i64,ctypes.POINTER(i64),ctypes.c_long,ctypes.POINTER(ctypes.c_char_p),ctypes.c_long]; lib.slang_record_mixed_filter_expr.restype=i64
    lib.slang_record_mixed_map_fields_expr.argtypes=[i64,ctypes.POINTER(i64),ctypes.c_long,ctypes.POINTER(ctypes.c_char_p),ctypes.c_long]; lib.slang_record_mixed_map_fields_expr.restype=i64
    lib.slang_record_mixed_get_number.argtypes=[i64,ctypes.c_long,ctypes.c_long]; lib.slang_record_mixed_get_number.restype=ctypes.c_double
    lib.slang_record_mixed_get_bool.argtypes=[i64,ctypes.c_long,ctypes.c_long]; lib.slang_record_mixed_get_bool.restype=ctypes.c_int
    lib.slang_record_mixed_get_text.argtypes=[i64,ctypes.c_long,ctypes.c_long]; lib.slang_record_mixed_get_text.restype=ctypes.c_char_p
    lib.slang_record_mixed_count.argtypes=[i64]; lib.slang_record_mixed_count.restype=ctypes.c_long
    lib.slang_record_mixed_free.argtypes=[i64]

    types=(i64*4)(2,0,1,0)
    values=(i64*12)(0,bits(20),1,bits(90), 0,bits(30),0,bits(70), 0,bits(40),1,bits(95))
    names=[b'Alice',b'Bob',b'Alice']
    text_ptrs=(i64*12)()
    for r,name in enumerate(names):
        text_ptrs[r*4]=ctypes.cast(ctypes.c_char_p(name),ctypes.c_void_p).value
    src=lib.slang_record_mixed_new_flat(types,values,text_ptrs,4,3); assert src
    pool=(ctypes.c_char_p*1)(b'Alice')

    # active && name == "Alice" && score > age * 2
    prog=(i64*55)(
        3,2,1,0,0, 3,0,2,0,0, 23,0,0,0,0, 21,0,0,0,0, 16,0,0,0,0,
        3,3,0,0,0, 3,1,0,0,0, 1,0,0,0,bits(2), 6,0,0,0,0,
        10,0,0,0,0, 16,0,0,0,0,
    )
    filtered=lib.slang_record_mixed_filter_expr(src,prog,11,pool,1); assert filtered
    assert lib.slang_record_mixed_count(filtered)==2
    assert [lib.slang_record_mixed_get_number(filtered,1,i) for i in range(2)]==[20,40]

    # age := age+1; active := !active. Name and score remain unchanged.
    map_prog=(i64*35)(
        3,1,0,0,0, 1,0,0,0,bits(1), 4,0,0,0,0, 20,1,0,0,0,
        3,2,1,0,0, 18,0,0,0,0, 20,2,0,0,0,
    )
    mapped=lib.slang_record_mixed_map_fields_expr(filtered,map_prog,7,None,0); assert mapped
    assert [lib.slang_record_mixed_get_number(mapped,1,i) for i in range(2)]==[21,41]
    assert [lib.slang_record_mixed_get_bool(mapped,2,i) for i in range(2)]==[0,0]
    assert [lib.slang_record_mixed_get_text(mapped,0,i) for i in range(2)]==[b'Alice',b'Alice']
    lib.slang_record_mixed_free(mapped); lib.slang_record_mixed_free(filtered); lib.slang_record_mixed_free(src)
