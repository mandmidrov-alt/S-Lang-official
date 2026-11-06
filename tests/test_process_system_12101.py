import os
from pathlib import Path

from slang.stdlib import home_directory, temp_directory, executable_path, command_exists
from slang.stdlib.registry import get

def test_process_paths_and_discovery():
    assert Path(home_directory()).is_absolute()
    assert Path(temp_directory()).is_absolute()
    assert Path(executable_path()).is_absolute()
    assert Path(executable_path()).exists()
    assert command_exists(Path(os.environ.get("PYTHON", "python")).name) or command_exists("python3") or command_exists("python")

def test_process_paths_registry_contracts():
    for name in ("home_directory", "temp_directory", "executable_path", "command_exists"):
        assert get(name).effect == "IO"
