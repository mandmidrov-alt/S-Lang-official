import ctypes
import subprocess


def bits(v):
    import struct
    return struct.unpack('q', struct.pack('d', float(v)))[0]


def test_runtime_field_mask_preserves_schema_and_hides_unselected_fields(tmp_path):
    so = tmp_path / 'libslang_runtime.so'
    subprocess.run(['cc', '-shared', '-fPIC', 'runtime/slang_runtime.c', '-o', str(so), '-lm'], check=True)
    lib = ctypes.CDLL(str(so))
    I64 = ctypes.c_int64
    lib.slang_record_mixed_new_flat.argtypes = [ctypes.POINTER(I64), ctypes.POINTER(I64), ctypes.POINTER(I64), ctypes.c_long, ctypes.c_long]
    lib.slang_record_mixed_new_flat.restype = I64
    lib.slang_record_mixed_mask_fields.argtypes = [I64, ctypes.POINTER(I64), ctypes.c_long]
    lib.slang_record_mixed_mask_fields.restype = I64
    lib.slang_record_mixed_get_number.argtypes = [I64, ctypes.c_long, ctypes.c_long]
    lib.slang_record_mixed_get_number.restype = ctypes.c_double
    lib.slang_record_mixed_get_text.argtypes = [I64, ctypes.c_long, ctypes.c_long]
    lib.slang_record_mixed_get_text.restype = ctypes.c_char_p
    lib.slang_record_mixed_free.argtypes = [I64]

    types = (I64 * 3)(2, 0, 0)
    values = (I64 * 6)(0, bits(20), bits(90), 0, bits(30), bits(70))
    texts = (I64 * 6)(ctypes.cast(ctypes.c_char_p(b'Ada'), ctypes.c_void_p).value, 0, 0,
                      ctypes.cast(ctypes.c_char_p(b'Bob'), ctypes.c_void_p).value, 0, 0)
    src = lib.slang_record_mixed_new_flat(types, values, texts, 3, 2)
    selected = (I64 * 2)(0, 2)
    out = lib.slang_record_mixed_mask_fields(src, selected, 2)
    assert out
    assert lib.slang_record_mixed_get_text(out, 0, 0) == b'Ada'
    assert lib.slang_record_mixed_get_number(out, 2, 0) == 90.0
    assert lib.slang_record_mixed_get_number(out, 1, 0) == 0.0
    assert lib.slang_record_mixed_get_text(out, 0, 1) == b'Bob'
    assert lib.slang_record_mixed_get_number(out, 2, 1) == 70.0
    lib.slang_record_mixed_free(out)
    lib.slang_record_mixed_free(src)
