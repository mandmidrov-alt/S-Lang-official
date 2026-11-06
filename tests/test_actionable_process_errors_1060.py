import subprocess
import sys

import pytest

from slang.stdlib.process import run_program, run_program_timeout


def test_missing_program_error_explains_what_to_check():
    with pytest.raises(FileNotFoundError, match="check the program name and cwd"):
        run_program("slang-program-that-does-not-exist-1060", [])


def test_invalid_working_directory_error_is_actionable(tmp_path):
    with pytest.raises(FileNotFoundError, match="check the program name and cwd"):
        run_program(sys.executable, ["-c", "print('ok')"], str(tmp_path / "missing-cwd"))


def test_timeout_error_keeps_exception_type_and_adds_advice():
    with pytest.raises(subprocess.TimeoutExpired, match="increase the timeout or make the operation faster"):
        run_program_timeout(sys.executable, ["-c", "import time; time.sleep(1)"], 0.01)


def test_successful_program_output_contract_is_unchanged():
    result = run_program(sys.executable, ["-c", "print('ok')"])
    assert result == ["0", "ok\n", ""]
