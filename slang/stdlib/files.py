from __future__ import annotations

from pathlib import Path
import shutil


def file_size(path: str) -> int:
    return Path(path).stat().st_size


def is_file(path: str) -> bool:
    return Path(path).is_file()


def is_directory(path: str) -> bool:
    return Path(path).is_dir()


def list_directory(path: str) -> list[str]:
    return sorted(item.name for item in Path(path).iterdir())


def make_directory(path: str) -> bool:
    Path(path).mkdir(parents=False, exist_ok=False)
    return True


def remove_directory(path: str) -> bool:
    Path(path).rmdir()
    return True


def read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_text(path: str, value: str) -> bool:
    Path(path).write_text(value, encoding="utf-8")
    return True


def append_text(path: str, value: str) -> bool:
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(value)
    return True



def read(path: str) -> str:
    """Read UTF-8 text from a file (legacy language primitive)."""
    return read_text(path)


def write(path: str, value: str) -> bool:
    """Write UTF-8 text to a file (legacy language primitive)."""
    return write_text(path, value)


def exists(path: str) -> bool:
    """Return whether a filesystem path exists."""
    from pathlib import Path
    return Path(path).exists()

def read_lines(path: str) -> list[str]:
    return Path(path).read_text(encoding="utf-8").splitlines()


def write_lines(path: str, lines: list[str]) -> bool:
    Path(path).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return True


def remove_file(path: str) -> bool:
    Path(path).unlink()
    return True


def copy_file(source: str, destination: str) -> bool:
    """Copy one file to a destination path."""
    shutil.copy2(source, destination)
    return True


def move_file(source: str, destination: str) -> bool:
    """Move one file to a destination path."""
    shutil.move(source, destination)
    return True


def make_directories(path: str) -> bool:
    """Create a directory and all missing parent directories."""
    Path(path).mkdir(parents=True, exist_ok=False)
    return True


def list_files(path: str) -> list[str]:
    """List file names directly contained in a directory."""
    return sorted(item.name for item in Path(path).iterdir() if item.is_file())


def list_directories(path: str) -> list[str]:
    """List directory names directly contained in a directory."""
    return sorted(item.name for item in Path(path).iterdir() if item.is_dir())


def remove_directory_tree(path: str) -> bool:
    """Remove a directory and all of its contents."""
    shutil.rmtree(path)
    return True


def read_json(path: str):
    """Read and decode a UTF-8 JSON file."""
    import json
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str, value) -> bool:
    """Write a value as human-readable UTF-8 JSON."""
    import json
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return True
