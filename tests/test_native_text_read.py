import subprocess
import sys
from pathlib import Path

from slang.core import parse_file, validate, llvm_ir
from slang.backend import compile_program

ROOT = Path(__file__).resolve().parents[1]


def test_native_read_lowering():
    p = parse_file(Path(__file__).resolve().parent / 'fixtures' / 'nonexistent.sl') if False else None
    # Compile from a temporary source in the executable test below; this check
    # keeps the ABI contract explicit in generated LLVM.
    source = ROOT / 'tests' / '_native_read_probe.sl'
    source.write_text('let text = read("native_read.txt")\nshow text\n', encoding='utf-8')
    try:
        program = parse_file(source)
        validate(program)
        result = compile_program(program, 'native')
        assert '@slang_file_read' in result.lowered.text
        assert '@slang_text_free' in result.lowered.text
    finally:
        source.unlink(missing_ok=True)


def test_native_read_and_read_lines_build_and_run(tmp_path):
    data = tmp_path / 'input.txt'
    data.write_text('alpha\nbeta\ngamma\n', encoding='utf-8')
    source = tmp_path / 'read.sl'
    source.write_text(
        'let text = read("input.txt")\n'
        'let lines = read_lines("input.txt")\n'
        'show text\n'
        'show lines\n', encoding='utf-8')
    out = tmp_path / 'read'
    built = subprocess.run(
        [sys.executable, '-m', 'slang.cli', 'build', str(source), '-o', str(out), '--backend', 'native'],
        cwd=ROOT, capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    run = subprocess.run([str(out)], cwd=tmp_path, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert run.stdout.splitlines() == ['alpha', 'beta', 'gamma', '', 'alpha', 'beta', 'gamma']
