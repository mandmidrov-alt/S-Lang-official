import sys

from slang.stdlib.process import run_process_timeout, run_program_timeout
from slang.stdlib.registry import get
from slang.stdlib.catalog import entries


def test_run_process_timeout_success():
    result = run_process_timeout(f"{sys.executable} -c \"print(42)\"", 2)
    assert result[0] == "0"
    assert result[1].strip() == "42"
    assert result[2] == ""


def test_run_program_timeout_success():
    result = run_program_timeout(sys.executable, ["-c", "print('ok')"], 2, "")
    assert result[0] == "0"
    assert result[1].strip() == "ok"


def test_timeout_validation():
    try:
        run_process_timeout("echo ok", -1)
    except ValueError:
        pass
    else:
        raise AssertionError("negative timeout must fail")


def test_registry_catalog():
    assert get("run_process_timeout").effect == "IO"
    assert get("run_program_timeout").effect == "IO"
    names = {row["name"] for row in entries()}
    assert {"run_process_timeout", "run_program_timeout"} <= names
