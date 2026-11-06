import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run_native(source: str) -> list[str]:
    path = ROOT / 'tests' / '.native_sequence_case.sl'
    path.write_text(source, encoding='utf-8')
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'slang.cli', 'run', '--native', str(path)],
            cwd=ROOT, text=True, capture_output=True, timeout=20,
        )
        assert result.returncode == 0, result.stderr or result.stdout
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    finally:
        path.unlink(missing_ok=True)


def test_native_fixed_numeric_sequence_and_reduce():
    source = '''sequence values from 1 for 12 steps using value * 3 + 1
 total = values reduce 0 with acc + item
 show total
'''.replace('\n total', '\ntotal').replace('\n show', '\nshow')
    assert _run_native(source) == ['398574']


def test_native_fixed_numeric_sequence_matches_interpreter():
    source = """sequence values from 2 for 6 steps using value * 2 + 1
show values
"""
    native = _run_native(source)
    assert native == ["2", "5", "11", "23", "47", "95"]
