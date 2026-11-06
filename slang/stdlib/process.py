"""Process-context operations for S-Lang."""
from __future__ import annotations
import os, sys
from pathlib import Path

def arguments() -> list[str]:
    return list(sys.argv[1:])

def environment(name: str) -> str:
    return os.environ.get(name, "")


def environment_or(name: str, default: str) -> str:
    """Return an environment variable or a caller-provided fallback."""
    if not isinstance(name, str) or not isinstance(default, str):
        raise TypeError("environment_or expects Text name and Text default")
    if not name:
        raise ValueError("environment_or expects a non-empty name")
    return os.environ.get(name, default)


def argument_count() -> int:
    """Return the number of command-line arguments excluding the executable."""
    return len(sys.argv) - 1


def argument_at(index: int) -> str:
    """Return a command-line argument by zero-based index."""
    if isinstance(index, bool) or not isinstance(index, int):
        raise TypeError("argument_at expects Number index")
    args = sys.argv[1:]
    if index < 0 or index >= len(args):
        raise IndexError("argument_at index out of range")
    return args[index]


def has_environment(name: str) -> bool:
    """Return whether a process environment variable is defined."""
    if not isinstance(name, str):
        raise TypeError("has_environment expects Text name")
    if not name:
        raise ValueError("has_environment expects a non-empty name")
    return name in os.environ


def set_environment(name: str, value: str) -> bool:
    """Set a process environment variable for the current S-Lang process."""
    if not isinstance(name, str) or not isinstance(value, str):
        raise TypeError("set_environment expects Text name and Text value")
    if not name:
        raise ValueError("set_environment expects a non-empty name")
    os.environ[name] = value
    return True


def remove_environment(name: str) -> bool:
    """Remove a process environment variable if present."""
    if not isinstance(name, str):
        raise TypeError("remove_environment expects Text name")
    if not name:
        raise ValueError("remove_environment expects a non-empty name")
    return os.environ.pop(name, None) is not None




def _run_with_actionable_errors(subprocess, invocation, *, label: str, timeout=None):
    """Run a child process while keeping OS exception types and adding context."""
    try:
        return subprocess.run(**invocation)
    except FileNotFoundError as exc:
        detail = "the executable or working directory could not be found"
        raise FileNotFoundError(f"{label}: {detail}; check the program name and cwd") from exc
    except NotADirectoryError as exc:
        raise NotADirectoryError(f"{label}: a component of cwd or the executable path is not a directory") from exc
    except PermissionError as exc:
        raise PermissionError(f"{label}: permission was denied; check executable and working-directory permissions") from exc
    except subprocess.TimeoutExpired as exc:
        limit = timeout if timeout is not None else exc.timeout
        raise subprocess.TimeoutExpired(
            f"{label}: process exceeded the timeout limit; increase the timeout or make the operation faster",
            limit, output=exc.output, stderr=exc.stderr,
        ) from exc


def run_process(command: str) -> list[str]:
    """Run a shell command and return [exit_code, stdout, stderr] as text."""
    import subprocess
    if not isinstance(command, str):
        raise TypeError("run_process expects a Text command")
    completed = _run_with_actionable_errors(subprocess, {"args": command, "shell": True, "capture_output": True, "text": True}, label="run_process")
    return [str(completed.returncode), completed.stdout, completed.stderr]


def run_program(program: str, args: list[str], cwd: str = "") -> list[str]:
    """Run a program directly without a shell: [exit_code, stdout, stderr]."""
    import subprocess
    if not isinstance(program, str) or not isinstance(args, list) or not all(isinstance(x, str) for x in args):
        raise TypeError("run_program expects Text and List<Text>")
    if cwd and not isinstance(cwd, str):
        raise TypeError("run_program cwd expects Text")
    completed = _run_with_actionable_errors(subprocess, {"args": [program, *args], "cwd": (cwd or None), "capture_output": True, "text": True}, label=f"run_program({program!r})")
    return [str(completed.returncode), completed.stdout, completed.stderr]


def run_program_with_environment(program: str, args: list[str], cwd: str = "", environment: list[str] | None = None) -> list[str]:
    """Run a program directly with child-only KEY=VALUE environment overrides."""
    import subprocess
    if not isinstance(program, str) or not isinstance(args, list) or not all(isinstance(x, str) for x in args):
        raise TypeError("run_program_with_environment expects Text and List<Text>")
    if cwd and not isinstance(cwd, str):
        raise TypeError("run_program_with_environment cwd expects Text")
    if environment is None:
        environment = []
    if not isinstance(environment, list) or not all(isinstance(x, str) and "=" in x and x.split("=", 1)[0] for x in environment):
        raise TypeError("run_program_with_environment environment expects List<Text> of KEY=VALUE entries")
    env = dict(__import__("os").environ)
    for entry in environment:
        key, value = entry.split("=", 1)
        env[key] = value
    completed = _run_with_actionable_errors(subprocess, {"args": [program, *args], "cwd": (cwd or None), "env": env, "capture_output": True, "text": True}, label=f"run_program_with_environment({program!r})")
    return [str(completed.returncode), completed.stdout, completed.stderr]


def run_process_timeout(command: str, timeout_seconds: float) -> list[str]:
    """Run a shell command with a timeout: [exit_code, stdout, stderr]."""
    import subprocess
    if not isinstance(command, str):
        raise TypeError("run_process_timeout expects a Text command")
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
        raise TypeError("run_process_timeout expects Number timeout_seconds")
    if timeout_seconds < 0:
        raise ValueError("run_process_timeout expects non-negative timeout_seconds")
    completed = _run_with_actionable_errors(subprocess, {"args": command, "shell": True, "capture_output": True, "text": True, "timeout": timeout_seconds}, label="run_process_timeout", timeout=timeout_seconds)
    return [str(completed.returncode), completed.stdout, completed.stderr]


def run_program_timeout(program: str, args: list[str], timeout_seconds: float, cwd: str = "") -> list[str]:
    """Run a program directly with a timeout: [exit_code, stdout, stderr]."""
    import subprocess
    if not isinstance(program, str) or not isinstance(args, list) or not all(isinstance(x, str) for x in args):
        raise TypeError("run_program_timeout expects Text and List<Text>")
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
        raise TypeError("run_program_timeout expects Number timeout_seconds")
    if timeout_seconds < 0:
        raise ValueError("run_program_timeout expects non-negative timeout_seconds")
    if not isinstance(cwd, str):
        raise TypeError("run_program_timeout cwd expects Text")
    completed = _run_with_actionable_errors(subprocess, {"args": [program, *args], "cwd": (cwd or None), "capture_output": True, "text": True, "timeout": timeout_seconds}, label=f"run_program_timeout({program!r})", timeout=timeout_seconds)
    return [str(completed.returncode), completed.stdout, completed.stderr]


def current_directory() -> str:
    """Return the host process current working directory."""
    return os.getcwd()


def platform_name() -> str:
    """Return the host platform family as a stable short name."""
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform.startswith("freebsd"):
        return "freebsd"
    return sys.platform


def process_id() -> float:
    """Return the current operating-system process identifier."""
    return float(os.getpid())


def sleep_seconds(seconds: float) -> bool:
    """Pause the current S-Lang process for the requested number of seconds."""
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        raise TypeError("sleep_seconds expects Number seconds")
    if seconds < 0:
        raise ValueError("sleep_seconds expects non-negative seconds")
    import time
    time.sleep(seconds)
    return True


def home_directory() -> str:
    """Return the current user's home directory."""
    return str(Path.home())


def temp_directory() -> str:
    """Return the host operating system temporary directory."""
    import tempfile
    return tempfile.gettempdir()


def executable_path() -> str:
    """Return the absolute path of the running Python/S-Lang host executable."""
    return str(Path(sys.executable).resolve())


def command_exists(command: str) -> bool:
    """Return whether an executable command is discoverable on PATH."""
    import shutil
    if not isinstance(command, str):
        raise TypeError("command_exists expects Text command")
    if not command:
        raise ValueError("command_exists expects a non-empty command")
    return shutil.which(command) is not None
