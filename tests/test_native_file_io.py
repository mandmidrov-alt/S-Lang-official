from pathlib import Path
import subprocess
import sys

from slang.core import parse_file, validate, llvm_ir
from slang.backend import compile_program


def test_native_file_io_lowering(tmp_path):
    source = tmp_path / "file_io.sl"
    source.write_text(
        'let path = "native.txt"\n'
        'let written = write(path, "hello")\n'
        'let present = exists(path)\n'
        'let size = file_size(path)\n'
        'let regular = is_file(path)\n'
        'show written, present, size, regular\n',
        encoding="utf-8",
    )
    p = parse_file(source)
    validate(p)
    result = compile_program(p, "native")
    assert result.lowered.backend == "native-llvm"
    assert "@slang_file_write" in result.lowered.text
    assert "@slang_file_exists" in result.lowered.text
    assert "@slang_file_size" in result.lowered.text
    assert "@slang_is_file" in result.lowered.text


def test_native_file_io_build_and_run(tmp_path):
    source = tmp_path / "file_io.sl"
    source.write_text(
        'let path = "native.txt"\n'
        'let written = write(path, "hello")\n'
        'let present = exists(path)\n'
        'let size = file_size(path)\n'
        'let regular = is_file(path)\n'
        'show written, present, size, regular\n',
        encoding="utf-8",
    )
    out = tmp_path / "file_io"
    subprocess.run(
        [sys.executable, "-m", "slang.cli", "build", str(source), "-o", str(out), "--backend", "native"],
        check=True,
        capture_output=True,
        text=True,
    )
    completed = subprocess.run([str(out)], cwd=tmp_path, check=True, capture_output=True, text=True)
    assert completed.stdout.splitlines() == ["true", "true", "5", "true"]
    assert (tmp_path / "native.txt").read_text(encoding="utf-8") == "hello"
