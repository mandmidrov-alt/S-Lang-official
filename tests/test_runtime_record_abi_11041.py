import ctypes
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_runtime(tmp_path):
    lib = tmp_path / "libslang_runtime.so"
    subprocess.run([
        "cc", "-shared", "-fPIC", "-O2", "runtime/slang_runtime.c", "-o", str(lib), "-lm"
    ], cwd=ROOT, check=True)
    return ctypes.CDLL(str(lib))


def test_record_f64_filter_preserves_all_columns(tmp_path):
    lib = build_runtime(tmp_path)
    lib.slang_record_f64_new.argtypes = [ctypes.POINTER(ctypes.POINTER(ctypes.c_double)), ctypes.c_long, ctypes.c_long]
    lib.slang_record_f64_new.restype = ctypes.c_int64
    lib.slang_record_f64_filter.argtypes = [ctypes.c_int64, ctypes.c_long, ctypes.c_double, ctypes.c_int]
    lib.slang_record_f64_filter.restype = ctypes.c_int64
    lib.slang_record_f64_get.argtypes = [ctypes.c_int64, ctypes.c_long, ctypes.c_long]
    lib.slang_record_f64_get.restype = ctypes.c_double
    lib.slang_record_f64_free.argtypes = [ctypes.c_int64]

    a = (ctypes.c_double * 3)(10, 20, 30)
    b = (ctypes.c_double * 3)(1, 2, 3)
    cols = (ctypes.POINTER(ctypes.c_double) * 2)(a, b)
    src = lib.slang_record_f64_new(cols, 2, 3)
    out = lib.slang_record_f64_filter(src, 0, 15.0, 1)
    assert [lib.slang_record_f64_get(out, 0, i) for i in range(2)] == [20.0, 30.0]
    assert [lib.slang_record_f64_get(out, 1, i) for i in range(2)] == [2.0, 3.0]
    lib.slang_record_f64_free(out)
    lib.slang_record_f64_free(src)


def test_record_f64_map_then_filter_keeps_handle_composable(tmp_path):
    lib = build_runtime(tmp_path)
    for name, args, restype in [
        ("slang_record_f64_new", [ctypes.POINTER(ctypes.POINTER(ctypes.c_double)), ctypes.c_long, ctypes.c_long], ctypes.c_int64),
        ("slang_record_f64_map_field", [ctypes.c_int64, ctypes.c_long, ctypes.c_double, ctypes.c_int], ctypes.c_int64),
        ("slang_record_f64_filter", [ctypes.c_int64, ctypes.c_long, ctypes.c_double, ctypes.c_int], ctypes.c_int64),
        ("slang_record_f64_get", [ctypes.c_int64, ctypes.c_long, ctypes.c_long], ctypes.c_double),
        ("slang_record_f64_free", [ctypes.c_int64], None),
    ]:
        fn = getattr(lib, name); fn.argtypes = args; fn.restype = restype
    a = (ctypes.c_double * 3)(10, 20, 30)
    b = (ctypes.c_double * 3)(1, 2, 3)
    cols = (ctypes.POINTER(ctypes.c_double) * 2)(a, b)
    src = lib.slang_record_f64_new(cols, 2, 3)
    mapped = lib.slang_record_f64_map_field(src, 0, 5.0, 1)
    filtered = lib.slang_record_f64_filter(mapped, 0, 25.0, 1)
    assert [lib.slang_record_f64_get(filtered, 0, i) for i in range(2)] == [25.0, 35.0]
    assert [lib.slang_record_f64_get(filtered, 1, i) for i in range(2)] == [2.0, 3.0]
    lib.slang_record_f64_free(filtered); lib.slang_record_f64_free(mapped); lib.slang_record_f64_free(src)


def test_record_f64_new_flat_materializes_row_major_source(tmp_path):
    lib = build_runtime(tmp_path)
    lib.slang_record_f64_new_flat.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_long, ctypes.c_long]
    lib.slang_record_f64_new_flat.restype = ctypes.c_int64
    lib.slang_record_f64_get.argtypes = [ctypes.c_int64, ctypes.c_long, ctypes.c_long]
    lib.slang_record_f64_get.restype = ctypes.c_double
    lib.slang_record_f64_free.argtypes = [ctypes.c_int64]
    flat = (ctypes.c_double * 6)(20, 50, 30, 80, 40, 90)
    src = lib.slang_record_f64_new_flat(flat, 2, 3)
    assert [lib.slang_record_f64_get(src, 0, i) for i in range(3)] == [20.0, 30.0, 40.0]
    assert [lib.slang_record_f64_get(src, 1, i) for i in range(3)] == [50.0, 80.0, 90.0]
    lib.slang_record_f64_free(src)

def test_record_f64_field_compare_and_binary_map(tmp_path):
    src = r'''
#include <stdint.h>
#include <stdio.h>
extern int64_t slang_record_f64_new_flat(const double*, long, long);
extern int64_t slang_record_f64_filter_field_compare(int64_t,long,long,double,int);
extern int64_t slang_record_f64_map_field_binary(int64_t,long,long,int);
extern double slang_record_f64_get(int64_t,long,long);
extern void slang_record_f64_free(int64_t);
int main(void){
    double data[] = {20,50, 30,70, 40,95};
    int64_t a=slang_record_f64_new_flat(data,2,3);
    int64_t b=slang_record_f64_filter_field_compare(a,1,0,2.0,0);
    int64_t c=slang_record_f64_map_field_binary(b,1,0,1);
    printf("%g %g\n", slang_record_f64_get(c,0,0), slang_record_f64_get(c,1,0));
    slang_record_f64_free(c); slang_record_f64_free(b); slang_record_f64_free(a); return 0;
}
'''
    cfile=tmp_path/'t.c'; exe=tmp_path/'t'; cfile.write_text(src)
    import subprocess
    root=__import__('pathlib').Path(__file__).resolve().parents[1]
    subprocess.run(['cc','-shared','-fPIC','runtime/slang_runtime.c','-o',str(tmp_path/'libslang.so'),'-lm'],cwd=root,check=True)
    # compile the small executable against the runtime source directly
    subprocess.run(['cc',str(cfile),'runtime/slang_runtime.c','-lm','-o',str(exe)],cwd=root,check=True)
    out=subprocess.check_output([str(exe)],cwd=root,text=True).strip()
    assert out == '20 30'
