from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_native_jit_executes_without_external_compiler(tmp_path):
    source = tmp_path / "jit.sl"
    source.write_text(
        "data numbers:\n"
        "    a value 1\n"
        "    b value 2\n"
        "    c value 3\n\n"
        "total = numbers sum value\n"
        "show total\n",
        encoding="utf-8",
    )
    env = dict(__import__('os').environ)
    env["PATH"] = ""  # prove that slang's JIT path does not find clang/gcc.
    completed = subprocess.run(
        [sys.executable, "-m", "slang.cli", "run", "--native-jit", str(source)],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "6"


def test_native_jit_executes_scalar_power_expression(tmp_path):
    source = tmp_path / "scalar_power.sl"
    source.write_text("show 2 ^ 3\n", encoding="utf-8")
    env = dict(__import__('os').environ)
    env["PATH"] = ""
    completed = subprocess.run(
        [sys.executable, "-m", "slang.cli", "run", "--native-jit", str(source)],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "8"


def test_native_jit_executes_multiple_scalar_shows_with_precedence(tmp_path):
    source = tmp_path / "scalar_precedence.sl"
    source.write_text(
        "show 2 + 3 * 4\n"
        "show (2 + 3) * 4\n"
        "show 2 ^ 3 ^ 2\n",
        encoding="utf-8",
    )
    env = dict(__import__('os').environ)
    env["PATH"] = ""
    completed = subprocess.run(
        [sys.executable, "-m", "slang.cli", "run", "--native-jit", str(source)],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == ["14", "20", "512"]


def test_native_jit_executes_power_in_fused_map_reduce(tmp_path):
    source = tmp_path / "fused_power.sl"
    source.write_text(
        "data numbers:\n"
        "    a value 2\n"
        "    b value 3\n\n"
        "filtered = numbers where value >= 1\n"
        "squares = filtered map value ^ 2\n"
        "total = squares reduce 0 with acc + item\n"
        "show total\n",
        encoding="utf-8",
    )
    env = dict(__import__('os').environ)
    env["PATH"] = ""
    completed = subprocess.run(
        [sys.executable, "-m", "slang.cli", "run", "--native-jit", str(source)],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "13"



def test_native_jit_reports_missing_csv_runtime_instead_of_crashing(tmp_path):
    csv = tmp_path / "scores.csv"
    csv.write_text("name,score\na,3\nb,1\n", encoding="utf-8")
    source = tmp_path / "csv_sort.sl"
    source.write_text(
        f'let rows = read_csv("{csv.as_posix()}")\n'
        'sorted = rows |> sort by row.score asc\n'
        'show sorted\n',
        encoding="utf-8",
    )
    env = dict(__import__("os").environ)
    env["PATH"] = ""
    completed = subprocess.run(
        [sys.executable, "-m", "slang.cli", "run", "--native-jit", str(source)],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )
    assert completed.returncode != 0
    assert "runtime symbols unavailable" in completed.stderr
    assert "slang_csv_open" in completed.stderr


def test_packaging_script_embeds_native_runtime_library():
    script = (ROOT / "packaging" / "build-runtime.py").read_text(encoding="utf-8")
    assert "native_runtime_for_current_platform" in script
    assert '"--add-binary"' in script
    assert "slang/native_runtime" in script
    assert 'binary_separator = ";" if platform.system() == "Windows" else ":"' in script


def test_runtime_sources_include_native_csv_sort_abi():
    runtime = (ROOT / "slang" / "slang_runtime.c").read_text(encoding="utf-8")
    packaged_source = (ROOT / "runtime" / "slang_runtime.c").read_text(encoding="utf-8")
    assert runtime == packaged_source
    assert "int64_t slang_csv_open(" in runtime
    assert "int slang_csv_sort_print(" in runtime


def test_native_jit_executes_unary_arithmetic_and_signed_exponent(tmp_path):
    source = tmp_path / "unary_arithmetic.sl"
    source.write_text(
        "show -5\n"
        "show +5\n"
        "show -2 ^ 2\n"
        "show 2 ^ -2\n",
        encoding="utf-8",
    )
    env = dict(__import__("os").environ)
    env["PATH"] = ""
    completed = subprocess.run(
        [sys.executable, "-m", "slang.cli", "run", "--native-jit", str(source)],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == ["-5", "5", "-4", "0.25"]


def test_native_jit_executes_modulo_with_truncation_remainder(tmp_path):
    source = tmp_path / "modulo.sl"
    source.write_text(
        "show 7 % 3\n"
        "show -7 % 3\n"
        "show 7 % -3\n",
        encoding="utf-8",
    )
    env = dict(__import__("os").environ)
    env["PATH"] = ""
    completed = subprocess.run(
        [sys.executable, "-m", "slang.cli", "run", "--native-jit", str(source)],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == ["1", "-1", "1"]


def test_native_jit_uses_windows_ucrt_instead_of_null_cdll(monkeypatch):
    from slang import native_jit

    calls = []

    class FakeLibrary:
        pass

    monkeypatch.setattr(native_jit.os, "name", "nt")
    monkeypatch.setattr(
        native_jit.ctypes,
        "CDLL",
        lambda name: calls.append(name) or FakeLibrary(),
    )

    native_jit._load_process_library()
    assert calls == ["ucrtbase.dll"]


def test_native_jit_uses_process_image_on_posix(monkeypatch):
    from slang import native_jit

    calls = []

    class FakeLibrary:
        pass

    monkeypatch.setattr(native_jit.os, "name", "posix")
    monkeypatch.setattr(
        native_jit.ctypes,
        "CDLL",
        lambda name: calls.append(name) or FakeLibrary(),
    )

    native_jit._load_process_library()
    assert calls == [None]
