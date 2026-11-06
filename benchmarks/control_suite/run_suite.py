from pathlib import Path
import subprocess, sys, json, re

ROOT = Path(__file__).resolve().parents[2]
TASKS = [
    ("sales_pipeline", "01_sales"),
    ("student_ranking", "02_students"),
    ("inventory_aggregation", "03_inventory"),
    ("two_body_physics", "04_physics"),
    ("circle_geometry", "05_geometry"),
]

def run(cmd):
    return subprocess.check_output(cmd, cwd=ROOT, text=True).strip()

def lines(path):
    return [x for x in path.read_text().splitlines() if x.strip() and not x.lstrip().startswith('#')]

def metrics(path):
    text = path.read_text()
    ls = lines(path)
    return {
        "lines": len(ls),
        "explicit_loops": len(re.findall(r'\bfor\s+(?:\w+\s+in|auto\s+|\()|\bwhile\s*\([^)]*\)', text)),
        "list_comprehensions": len(re.findall(r'\[.*?for .*? in .*?\]', text, re.S)),
        "lambda": len(re.findall(r'\blambda\b', text)),
        "manual_accumulator": len(re.findall(r'\b(total|acc|sum|average|avg)\b', text)),
        "indexing": len(re.findall(r'\[[0-9]+\]', text)),
    }

rows=[]
for name, stem in TASKS:
    sl = ROOT/'benchmarks/control_suite/tasks'/f'{stem}.sl'
    py = ROOT/'benchmarks/control_suite/tasks'/f'{stem}.py'
    cpp = ROOT/'benchmarks/control_suite/tasks'/f'{stem}.cpp'
    sout = run([sys.executable, '-m', 'slang.cli', 'run', str(sl)])
    pout = run([sys.executable, str(py)])
    # C++ reference is used as a semantic cross-check; it may format floats differently.
    import shutil, tempfile, os
    compiler = shutil.which('clang++') or shutil.which('g++')
    cout = None
    if compiler:
        exe = ROOT/'benchmarks/control_suite'/f'.{stem}_cpp'
        subprocess.run([compiler, '-O2', str(cpp), '-o', str(exe)], cwd=ROOT, check=True)
        cout = run([str(exe)])
        exe.unlink(missing_ok=True)
    rows.append({
        "task": name,
        "outputs": {"slang": sout, "python": pout, "cpp": cout},
        "metrics": {"slang": metrics(sl), "python": metrics(py), "cpp": metrics(cpp)},
    })

out = ROOT/'benchmarks/control_suite/results.json'
out.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
print(json.dumps(rows, indent=2, ensure_ascii=False))
