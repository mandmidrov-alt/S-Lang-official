"""Fair scaling comparison for S-Lang, Python and C++.

The benchmark uses the same generated CSV data and the same algorithm in all
three languages. C++ is compiled once with -O2; compilation time is reported
separately and is never mixed into steady-state runtime. S-Lang native support
is attempted separately and is reported as unavailable when the current native
lowering cannot represent the complete CSV pipeline.
"""
from __future__ import annotations

import csv
import json
import os
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIZES = (1_000, 5_000, 10_000, 50_000)
REPEATS = 3

SLANG_SOURCE = '''let rows = read_csv("DATASET")\nadults = rows where to_number(item.age) >= 18\nengineers = adults where item.role == "engineer"\nscores = engineers map to_number(item.score)\ntotal = scores reduce 0 with acc + item\nshow total\n'''
PYTHON_SOURCE = '''import csv\nwith open("DATASET", newline="", encoding="utf-8") as f:\n    rows = list(csv.DictReader(f))\nadults = [r for r in rows if int(r["age"]) >= 18]\nengineers = [r for r in adults if r["role"] == "engineer"]\nscores = [int(r["score"]) for r in engineers]\nprint(sum(scores))\n'''
CPP_SOURCE = r'''#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
int main(int argc, char** argv) {
    std::ifstream in(argv[1]); std::string line; std::getline(in, line);
    long long total = 0;
    while (std::getline(in, line)) {
        std::stringstream ss(line); std::string x, role; int age, score;
        std::getline(ss, x, ','); std::getline(ss, x, ','); age = std::stoi(x);
        std::getline(ss, x, ','); score = std::stoi(x); std::getline(ss, role, ',');
        if (!role.empty() && role.back() == '\r') role.pop_back();
        if (age >= 18 && role == "engineer") total += score;
    }
    std::cout << total << "\n";
}
'''


def make_csv(path: Path, n: int) -> int:
    expected = 0
    with path.open("w", newline="", encoding="utf-8") as f:
        out = csv.writer(f)
        out.writerow(("name", "age", "score", "role"))
        for i in range(n):
            age = 18 + (i % 50)
            score = 100 + (i % 900)
            role = "engineer" if i % 3 == 0 else "artist"
            out.writerow((f"p{i}", age, score, role))
            if age >= 18 and role == "engineer":
                expected += score
    return expected


def timed(cmd: list[str], cwd: Path) -> tuple[float, str]:
    start = time.perf_counter()
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    elapsed = time.perf_counter() - start
    if proc.returncode:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{proc.stderr}")
    return elapsed, proc.stdout.strip()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="slang-scale-") as td:
        work = Path(td)
        cpp = work / "bench.cpp"
        cpp.write_text(CPP_SOURCE, encoding="utf-8")
        binary = work / "bench_cpp"
        build_start = time.perf_counter()
        build = subprocess.run(["g++", "-O2", "-std=c++17", str(cpp), "-o", str(binary)], cwd=ROOT, text=True, capture_output=True)
        cpp_build = time.perf_counter() - build_start
        if build.returncode:
            raise RuntimeError(build.stderr)

        results = []
        for n in SIZES:
            data = work / f"people_{n}.csv"
            expected = make_csv(data, n)
            sl = work / "bench.sl"; py = work / "bench.py"
            sl.write_text(SLANG_SOURCE.replace("DATASET", str(data)), encoding="utf-8")
            py.write_text(PYTHON_SOURCE.replace("DATASET", str(data)), encoding="utf-8")
            row = {"rows": n, "expected": expected}
            for name, cmd in (
                ("slang_interpreter", ["python", "-m", "slang.cli", "run", str(sl)]),
                ("python", ["python", str(py)]),
                ("cpp", [str(binary), str(data)]),
            ):
                times, outputs = [], []
                for _ in range(REPEATS):
                    t, out = timed(cmd, ROOT)
                    times.append(t); outputs.append(out)
                normalized = outputs[0].split("=")[-1].strip() if name == "slang_interpreter" else outputs[0]
                if len(set(outputs)) != 1 or int(float(normalized)) != expected:
                    raise AssertionError(f"{name} result mismatch at {n}: {outputs}, expected {expected}")
                row[name] = {"median_seconds": statistics.median(times), "min_seconds": min(times), "deterministic": len(set(outputs)) == 1}
            # Native S-Lang is intentionally a separate capability check.
            native_out = work / f"bench_native_{n}"
            native_build_start = time.perf_counter()
            native = subprocess.run(["python", "-m", "slang.cli", "build", str(sl), "-o", str(native_out), "--backend", "native"], cwd=ROOT, text=True, capture_output=True)
            native_build = time.perf_counter() - native_build_start
            if native.returncode == 0:
                ntimes, noutputs = [], []
                for _ in range(REPEATS):
                    t, out = timed([str(native_out)], ROOT)
                    ntimes.append(t); noutputs.append(out)
                if len(set(noutputs)) != 1 or int(float(noutputs[0])) != expected:
                    raise AssertionError(f"slang_native result mismatch at {n}: {noutputs}, expected {expected}")
                row["slang_native"] = {"available": True, "build_seconds": native_build, "median_seconds": statistics.median(ntimes), "min_seconds": min(ntimes), "deterministic": True}
            else:
                row["slang_native"] = {"available": False, "build_seconds": native_build, "diagnostic": native.stderr.strip()}
            results.append(row)
        print(json.dumps({"repeats": REPEATS, "cpp_build_seconds": cpp_build, "results": results}, indent=2))


if __name__ == "__main__":
    main()
