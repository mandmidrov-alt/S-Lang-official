"""Native multi-aggregate parity for numeric and Record collections."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_run(tmp_path, source):
    src = tmp_path / "multi_aggregate.sl"
    out = tmp_path / "multi_aggregate"
    src.write_text(source, encoding="utf-8")
    build = subprocess.run(
        [sys.executable, "-m", "slang.cli", "build", str(src), "-o", str(out), "--backend", "native"],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    return run.stdout.splitlines()


def test_native_number_list_multiple_aggregates_share_one_scan(tmp_path):
    assert build_run(tmp_path, '''
let values = [1, 2, 3, 4]
total = values sum item
counted = values count
minimum = values min item
maximum = values max item
mean = values average item
show total
show counted
show minimum
show maximum
show mean
''') == ["10", "4", "1", "4", "2.5"]


def test_native_record_multiple_aggregates_share_one_scan(tmp_path):
    assert build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    score: Number

let people = [Person("Ada", 36, 8), Person("Bob", 15, 5), Person("Lin", 27, 9)]
total = people sum row.age
counted = people count
minimum = people min row.score
maximum = people max row.age
mean = people average row.score
show total
show counted
show minimum
show maximum
show mean
''') == ["78", "3", "5", "36", "7.333333333333333"]


def test_native_record_filter_map_multiple_aggregates_share_one_scan(tmp_path):
    assert build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    active: Boolean

let people = [Person("Ada", 36, true), Person("Bob", 15, false), Person("Lin", 27, true)]
selected = people where row.active == true
ages = selected map row.age
total = ages sum item
counted = ages count
minimum = ages min item
maximum = ages max item
mean = ages average item
show total
show counted
show minimum
show maximum
show mean
''') == ["63", "2", "27", "36", "31.5"]


def test_native_function_map_multiple_aggregates_share_one_scan(tmp_path):
    assert build_run(tmp_path, '''
function double(x: Number) -> Number:
    return x * 2

data numbers:
    a value 1
    b value 2
    c value 3

scaled = numbers map double(row.value)
total = scaled sum item
counted = scaled count
minimum = scaled min item
maximum = scaled max item
mean = scaled average item
show total
show counted
show minimum
show maximum
show mean
''') == ["12", "3", "2", "6", "4"]


def test_native_sorted_record_multiple_aggregates_share_one_scan(tmp_path):
    assert build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    score: Number

let people = [Person("Lin", 27, 9), Person("Ada", 36, 8), Person("Bob", 15, 5)]
ordered = people sort by row.age asc
total = ordered sum row.age
counted = ordered count
minimum = ordered min row.score
maximum = ordered max row.age
mean = ordered average row.score
show total
show counted
show minimum
show maximum
show mean
''') == ["78", "3", "5", "36", "7.33333333333333"]


def test_native_record_boolean_projection_multiple_aggregates(tmp_path):
    assert build_run(tmp_path, '''
record Person:
    name: Text
    active: Boolean

let people = [Person("Ada", true), Person("Bob", false), Person("Lin", true)]
flags = people map row.active
counted = flags count item
present = flags any item
all_present = flags all item
show counted
show present
show all_present
''') == ["3", "true", "false"]


def test_native_record_multi_aggregate_ir_has_one_shared_loop(tmp_path):
    src = tmp_path / "record_multi_ir.sl"
    src.write_text('''
record Person:
    name: Text
    age: Number
    score: Number

let people = [Person("Ada", 36, 8), Person("Bob", 15, 5), Person("Lin", 27, 9)]
ordered = people sort by row.age asc
total = ordered sum row.age
counted = ordered count
minimum = ordered min row.score
maximum = ordered max row.age
mean = ordered average row.score
show total
show counted
show minimum
show maximum
show mean
''', encoding="utf-8")
    emitted = subprocess.run(
        [sys.executable, "-m", "slang.cli", "emit-llvm", str(src)],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert emitted.returncode == 0, emitted.stderr
    assert emitted.stdout.count("multi_agg_loop:") == 1
    assert emitted.stdout.count("multi_agg_body:") == 1
