import ctypes, subprocess, struct


def bits(v):
    return struct.unpack('q', struct.pack('d', float(v)))[0]


def test_runtime_mixed_unified_transform_combines_projection_and_computation():
    so='/tmp/libslang_11051.so'
    subprocess.run(['cc','-shared','-fPIC','runtime/slang_runtime.c','-o',so,'-lm'],check=True)
    lib=ctypes.CDLL(so); i64=ctypes.c_int64
    lib.slang_record_mixed_new_flat.argtypes=[ctypes.POINTER(i64),ctypes.POINTER(i64),ctypes.POINTER(i64),ctypes.c_long,ctypes.c_long]; lib.slang_record_mixed_new_flat.restype=i64
    lib.slang_record_mixed_map_to_schema_expr.argtypes=[i64,ctypes.POINTER(i64),ctypes.c_long,ctypes.POINTER(i64),ctypes.c_long,ctypes.POINTER(ctypes.c_char_p),ctypes.c_long]; lib.slang_record_mixed_map_to_schema_expr.restype=i64
    lib.slang_record_mixed_get_text.argtypes=[i64,ctypes.c_long,ctypes.c_long]; lib.slang_record_mixed_get_text.restype=ctypes.c_char_p
    lib.slang_record_mixed_get_number.argtypes=[i64,ctypes.c_long,ctypes.c_long]; lib.slang_record_mixed_get_number.restype=ctypes.c_double
    lib.slang_record_mixed_get_bool.argtypes=[i64,ctypes.c_long,ctypes.c_long]; lib.slang_record_mixed_get_bool.restype=ctypes.c_int
    lib.slang_record_mixed_free.argtypes=[i64]

    # Person: name(Text), age(Number), active(Boolean), score(Number)
    types=(i64*4)(2,0,1,0)
    vals=(i64*8)(0,bits(20),1,bits(90),0,bits(30),0,bits(70))
    text=(i64*8)()
    text[0]=ctypes.cast(ctypes.c_char_p(b'Alice'),ctypes.c_void_p).value
    text[4]=ctypes.cast(ctypes.c_char_p(b'Bob'),ctypes.c_void_p).value
    src=lib.slang_record_mixed_new_flat(types,vals,text,4,2); assert src

    # Final: ok(Boolean), value(Number), label(Text)
    target=(i64*3)(1,0,2)
    # target0 <- source2 (direct opcode 26)
    # target1 <- source3 - source1
    # target2 <- source0 (direct opcode 26)
    prog=(i64*30)(
        26,0,2,0,0,
        3,3,0,0,0, 3,1,0,0,0, 5,0,0,0,0, 20,1,0,0,0,
        26,2,0,0,0,
    )
    out=lib.slang_record_mixed_map_to_schema_expr(src,target,3,prog,6,None,0); assert out
    assert lib.slang_record_mixed_get_bool(out,0,0)==1
    assert lib.slang_record_mixed_get_bool(out,0,1)==0
    assert [lib.slang_record_mixed_get_number(out,1,i) for i in range(2)]==[70,40]
    assert [lib.slang_record_mixed_get_text(out,2,i) for i in range(2)]==[b'Alice',b'Bob']
    lib.slang_record_mixed_free(out); lib.slang_record_mixed_free(src)
