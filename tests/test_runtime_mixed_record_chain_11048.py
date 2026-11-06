import ctypes
import struct
import subprocess


def bits(v):
    return struct.unpack('q', struct.pack('d', float(v)))[0]


def test_runtime_mixed_schema_filter_schema_chain():
    so = '/tmp/libslang_11048.so'
    subprocess.run(['cc', '-shared', '-fPIC', 'runtime/slang_runtime.c', '-o', so, '-lm'], check=True)
    lib = ctypes.CDLL(so)
    i64 = ctypes.c_int64

    lib.slang_record_mixed_new_flat.argtypes = [ctypes.POINTER(i64), ctypes.POINTER(i64), ctypes.POINTER(i64), ctypes.c_long, ctypes.c_long]
    lib.slang_record_mixed_new_flat.restype = i64
    lib.slang_record_mixed_map_to_schema_expr.argtypes = [i64, ctypes.POINTER(i64), ctypes.c_long, ctypes.POINTER(i64), ctypes.c_long, ctypes.POINTER(ctypes.c_char_p), ctypes.c_long]
    lib.slang_record_mixed_map_to_schema_expr.restype = i64
    lib.slang_record_mixed_filter_expr.argtypes = [i64, ctypes.POINTER(i64), ctypes.c_long, ctypes.POINTER(ctypes.c_char_p), ctypes.c_long]
    lib.slang_record_mixed_filter_expr.restype = i64
    lib.slang_record_mixed_count.argtypes = [i64]
    lib.slang_record_mixed_count.restype = ctypes.c_long
    lib.slang_record_mixed_get_text.argtypes = [i64, ctypes.c_long, ctypes.c_long]
    lib.slang_record_mixed_get_text.restype = ctypes.c_char_p
    lib.slang_record_mixed_get_number.argtypes = [i64, ctypes.c_long, ctypes.c_long]
    lib.slang_record_mixed_get_number.restype = ctypes.c_double
    lib.slang_record_mixed_get_bool.argtypes = [i64, ctypes.c_long, ctypes.c_long]
    lib.slang_record_mixed_get_bool.restype = ctypes.c_int
    lib.slang_record_mixed_free.argtypes = [i64]

    src_types = (i64 * 4)(2, 0, 1, 0)
    vals = (i64 * 12)(
        0, bits(20), 1, bits(90),
        0, bits(30), 0, bits(70),
        0, bits(40), 1, bits(95),
    )
    text = (i64 * 12)()
    names = (b'Alice', b'Bob', b'Carol')
    name_ptrs = [ctypes.c_char_p(name) for name in names]
    for row, ptr in enumerate(name_ptrs):
        text[row * 4] = ctypes.cast(ptr, ctypes.c_void_p).value
    src = lib.slang_record_mixed_new_flat(src_types, vals, text, 4, 3)
    assert src

    # Person -> Summary(label: Text, value: Number).
    target_summary = (i64 * 2)(2, 0)
    map_summary = (i64 * 30)(
        3, 0, 2, 0, 0, 20, 0, 0, 0, 0,
        3, 3, 0, 0, 0,
        3, 1, 0, 0, 0,
        5, 0, 0, 0, 0,
        20, 1, 0, 0, 0,
    )
    summary = lib.slang_record_mixed_map_to_schema_expr(src, target_summary, 2, map_summary, 6, None, 0)
    assert summary

    # Summary -> filter value > 50.
    pred = (i64 * 15)(3, 1, 0, 0, 0, 1, 0, 0, 0, bits(50), 10, 0, 0, 0, 0)
    filtered = lib.slang_record_mixed_filter_expr(summary, pred, 3, None, 0)
    assert filtered
    assert lib.slang_record_mixed_count(filtered) == 2

    # Summary -> Final(label: Text, value: Number, ok: Boolean).
    target_final = (i64 * 3)(2, 0, 1)
    final_words = [
        3, 0, 2, 0, 0, 20, 0, 0, 0, 0,
        3, 1, 0, 0, 0, 1, 0, 0, 0, bits(1), 4, 0, 0, 0, 0, 20, 1, 0, 0, 0,
        3, 1, 0, 0, 0, 1, 0, 0, 0, bits(60), 10, 0, 0, 0, 0, 20, 2, 0, 0, 0,
    ]
    map_final = (i64 * len(final_words))(*final_words)
    final = lib.slang_record_mixed_map_to_schema_expr(filtered, target_final, 3, map_final, 10, None, 0)
    assert final
    assert lib.slang_record_mixed_count(final) == 2
    assert [lib.slang_record_mixed_get_text(final, 0, r) for r in range(2)] == [b'Alice', b'Carol']
    assert [lib.slang_record_mixed_get_number(final, 1, r) for r in range(2)] == [71.0, 56.0]
    assert [lib.slang_record_mixed_get_bool(final, 2, r) for r in range(2)] == [1, 0]

    lib.slang_record_mixed_free(final)
    lib.slang_record_mixed_free(filtered)
    lib.slang_record_mixed_free(summary)
    lib.slang_record_mixed_free(src)
