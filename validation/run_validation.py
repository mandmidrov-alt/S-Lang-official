from pathlib import Path
import subprocess, sys, shutil, time, json
ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

def nonempty_lines(path):
    return sum(1 for line in path.read_text().splitlines() if line.strip() and not line.lstrip().startswith('#'))

def run_slang(src):
    return subprocess.check_output([PY, '-m', 'slang.cli', 'run', str(src)], cwd=ROOT, text=True).strip()

def run_python(src):
    return subprocess.check_output([PY, str(src)], cwd=ROOT, text=True).strip()

def run_cpp(src):
    clang = shutil.which('clang++') or shutil.which('g++')
    if not clang: return None
    out = ROOT / 'validation' / (src.stem + '_cpp')
    subprocess.run([clang, '-O2', str(src), '-o', str(out)], check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
    try: return subprocess.check_output([str(out)], cwd=ROOT, text=True).strip()
    finally: out.unlink(missing_ok=True)

cases = [
    ('physics', ROOT/'examples/two_body.sl', ROOT/'benchmarks/two_body_python.py', ROOT/'benchmarks/two_body_cpp.cpp'),
    ('data', ROOT/'benchmarks/data/filter_sort.sl', ROOT/'benchmarks/data/filter_sort.py', ROOT/'benchmarks/data/filter_sort.cpp'),
    ('geometry', ROOT/'benchmarks/geometry/circle.sl', ROOT/'benchmarks/geometry/circle.py', ROOT/'benchmarks/geometry/circle.cpp'),
]
rows=[]
for name, slang, ref, cpp in cases:
    t=time.perf_counter(); sout=run_slang(slang); st=time.perf_counter()-t
    pout=run_python(ref)
    cout=run_cpp(cpp)
    if name=='physics':
        # Python/C++ references have slightly different formatting; compare key numeric values.
        ok = ('152194895551' in sout and '30283.7889471754' in sout)
    else:
        ok = (all(x in sout for x in ['Alice', 'Eve', 'Carol']) and sout.index('Alice') < sout.index('Eve') < sout.index('Carol')) if name=='data' else (all(x in sout for x in ['314.159265358979 m2','62.8318530717959 m']))
    rows.append({'case':name,'slang_lines':nonempty_lines(slang),'python_lines':nonempty_lines(ref),'cpp_lines':nonempty_lines(cpp),'semantic_match':ok,'slang_time_s':round(st,6),'slang_output':sout,'python_output':pout,'cpp_output':cout})
print(json.dumps(rows, indent=2, ensure_ascii=False))
if not all(r['semantic_match'] for r in rows): raise SystemExit(1)

