"""Native record-sort pipelines with scalar rebinding and shared aggregates."""
import subprocess
import sys
from pathlib import Path

from slang.core import llvm_ir, parse

ROOT = Path(__file__).resolve().parents[1]


def execute(tmp_path, source, native):
    path = tmp_path / ("native_pipeline.sl" if native else "interpreted_pipeline.sl")
    path.write_text(source, encoding="utf-8")
    if native:
        output = tmp_path / "native_pipeline"
        build = subprocess.run(
            [sys.executable, "-m", "slang.cli", "build", str(path), "-o", str(output), "--backend", "native"],
            cwd=ROOT, text=True, capture_output=True, timeout=90,
        )
        assert build.returncode == 0, build.stderr
        command = [str(output)]
    else:
        command = [sys.executable, "-m", "slang.cli", "run", str(path)]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def test_sorted_record_scalar_rebinding_pipeline_matches_interpreter(tmp_path):
    source = '''
record Person:
    age: Number
    score: Number
let people = [Person(36, 91), Person(15, 88), Person(27, 95), Person(42, 72), Person(20, 90)]
selected = people where row.age >= 18
ordered = selected sort by row.age asc
scores = ordered map row.score
scores = scores where item >= 80
scores = scores map item + 5
total = scores sum item
counted = scores count
minimum = scores min item
maximum = scores max item
mean = scores average item
show total
show counted
show minimum
show maximum
show mean
'''
    interpreted = execute(tmp_path, source, False)
    native = execute(tmp_path, source, True)
    assert interpreted == ["291", "3", "95", "100", "97"]
    assert native == interpreted


def test_sorted_record_multi_aggregate_uses_one_terminal_scan(tmp_path):
    source = '''
record Item:
    rank: Number
    amount: Number
let items = [Item(3, 12), Item(1, 20), Item(2, 16)]
ordered = items sort by row.rank asc
values = ordered map row.amount
values = values map item + 1
total = values sum item
counted = values count
minimum = values min item
maximum = values max item
show total
show counted
show minimum
show maximum
'''
    module = parse(source)
    ir = llvm_ir(module)
    assert "multi_agg_loop" in ir
    assert ir.count("multi_agg_loop:") == 1
