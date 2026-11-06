from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from slang.core import parse, llvm_ir

ROOT = Path(__file__).resolve().parents[1]

SOURCE_AGGREGATE = '''
record Address:
    city: Text
    code: Number
record Person:
    name: Text
    address: Address
let people = [Person("Ada", Address("A", 41)), Person("Bob", Address("B", 20)), Person("Lin", Address("C", 55))]
selected = people where row.address.code >= 40
ordered = selected sort by row.address.code desc
total = ordered sum row.address.code
show total
'''

SOURCE_REDUCE = SOURCE_AGGREGATE.replace('total = ordered sum row.address.code', 'total = ordered reduce 0 with acc + row.address.code')


def test_nested_sort_aggregate_ir():
    ir = llvm_ir(parse(SOURCE_AGGREGATE, ROOT))
    assert "ModuleID = 'slang-record-sort'" in ir
    assert 'rcs_address__code' in ir
    assert '5.50000000000000000e+01' in ir


def test_nested_sort_reduce_ir():
    ir = llvm_ir(parse(SOURCE_REDUCE, ROOT))
    assert "ModuleID = 'slang-record-sort'" in ir
    assert 'rcs_address__code' in ir
    assert 'slang_reduce_f64' in ir


def _build_and_run(tmp_path, source):
    src = tmp_path / 'nested_sort.sl'
    out = tmp_path / 'nested_sort'
    src.write_text(source, encoding='utf-8')
    proc = subprocess.run([sys.executable, '-m', 'slang.cli', 'build', str(src), '-o', str(out), '--backend', 'native'], cwd=ROOT, text=True, capture_output=True, timeout=45)
    assert proc.returncode == 0, proc.stderr
    run = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True, timeout=10)
    assert run.returncode == 0, run.stderr
    return run.stdout.splitlines()


def test_nested_sort_aggregate_executes_natively(tmp_path):
    assert _build_and_run(tmp_path, SOURCE_AGGREGATE) == ['96']


def test_nested_sort_reduce_executes_natively(tmp_path):
    assert _build_and_run(tmp_path, SOURCE_REDUCE) == ['96']
