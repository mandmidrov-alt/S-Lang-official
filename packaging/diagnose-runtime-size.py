#!/usr/bin/env python3

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist" / "diagnostic"
BUILD = ROOT / "build" / "pyinstaller-diagnostic"
ENTRY = ROOT / "packaging" / "pyinstaller" / "runtime_entry.py"


def run(command: list[str]) -> None:
    print()
    print("$", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def format_size(size: int) -> str:
    value = float(size)

    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:,.2f} {unit}"
        value /= 1024

    return f"{size:,} B"


def collect_files(root: Path) -> list[tuple[int, Path]]:
    files: list[tuple[int, Path]] = []

    for path in root.rglob("*"):
        if path.is_file():
            try:
                files.append((path.stat().st_size, path))
            except OSError:
                pass

    return files


def print_file_table(
    title: str,
    files: list[tuple[int, Path]],
    root: Path,
    limit: int = 50,
) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)

    total = sum(size for size, _ in files)

    print(f"Files: {len(files):,}")
    print(f"Total: {format_size(total)}")
    print()

    for size, path in sorted(files, reverse=True)[:limit]:
        relative = path.relative_to(root)
        print(f"{format_size(size):>14}  {relative}")


def print_matching_files(
    title: str,
    files: list[tuple[int, Path]],
    root: Path,
    predicate,
) -> None:
    matches = [
        (size, path)
        for size, path in files
        if predicate(path)
    ]

    print_file_table(title, matches, root, limit=100)


def print_directory_sizes(root: Path) -> None:
    directory_sizes: dict[Path, int] = {}

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        try:
            size = path.stat().st_size
        except OSError:
            continue

        current = path.parent

        while current >= root:
            directory_sizes[current] = directory_sizes.get(current, 0) + size

            if current == root:
                break

            current = current.parent

    print()
    print("=" * 80)
    print("DIRECTORY SIZES")
    print("=" * 80)

    for directory, size in sorted(
        directory_sizes.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:50]:
        relative = directory.relative_to(root)
        label = "." if str(relative) == "." else str(relative)
        print(f"{format_size(size):>14}  {label}")


def main() -> None:
    if platform.system() != "Linux":
        raise SystemExit(
            "This diagnostic is intended to run on Linux."
        )

    if not ENTRY.is_file():
        raise SystemExit(
            f"Entry point not found: {ENTRY}"
        )

    DIST.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--onedir",
        "--console",
        "--name",
        "slang-diagnostic",
        "--distpath",
        str(DIST),
        "--workpath",
        str(BUILD),
        "--specpath",
        str(BUILD),
        "--paths",
        str(ROOT),

        "--collect-submodules",
        "slang",

        "--collect-data",
        "slang",

        "--hidden-import",
        "llvmlite",

        "--hidden-import",
        "llvmlite.binding",

        "--hidden-import",
        "llvmlite.binding.ffi",

        "--collect-binaries",
        "llvmlite",

        str(ENTRY),
    ]

    run(command)

    app = DIST / "slang-diagnostic"

    if not app.is_dir():
        raise SystemExit(
            f"Diagnostic directory was not produced: {app}"
        )

    files = collect_files(app)

    total_size = sum(size for size, _ in files)

    print()
    print("=" * 80)
    print("S-LANG RUNTIME SIZE DIAGNOSTIC")
    print("=" * 80)
    print(f"Runtime: {app}")
    print(f"Total files: {len(files):,}")
    print(f"Total size: {format_size(total_size)}")

    print_file_table(
        "LARGEST FILES",
        files,
        app,
        limit=50,
    )

    print_directory_sizes(app)

    print_matching_files(
        "SHARED LIBRARIES",
        files,
        app,
        lambda path: (
            ".so" in path.name
            or path.name.endswith(".so")
        ),
    )

    print_matching_files(
        "LLVMLITE FILES",
        files,
        app,
        lambda path: "llvmlite" in str(path).lower(),
    )

    print_matching_files(
        "PYTHON FILES",
        files,
        app,
        lambda path: (
            path.suffix.lower() in {".py", ".pyc"}
        ),
    )

    print_matching_files(
        "LARGE NATIVE LIBRARIES (> 1 MB)",
        files,
        app,
        lambda path: (
            path.suffix in {".so", ".dylib"}
            or ".so." in path.name
        )
        and path.stat().st_size > 1024 * 1024,
    )

    print()
    print("=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
