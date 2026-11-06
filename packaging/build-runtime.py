#!/usr/bin/env python3
"""Build a self-contained S-Lang 1.0 executable for the current runner."""
from __future__ import annotations

import argparse
import importlib.metadata
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUILD = ROOT / "build" / "pyinstaller"
NATIVE_RUNTIME = ROOT / "slang" / "native_runtime"
ENTRY = ROOT / "packaging" / "pyinstaller" / "runtime_entry.py"
EXPECTED_BUILD_DEPENDENCIES = {
    "PyInstaller": "6.16.0",
    "llvmlite": "0.45.1",
}
MIN_PYTHON = (3, 10)
MAX_PYTHON = (3, 13)


def check_build_dependencies() -> None:
    """Fail early with actionable errors before compiling or freezing files."""
    current_python = sys.version_info[:2]
    if not MIN_PYTHON <= current_python <= MAX_PYTHON:
        supported = f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}–{MAX_PYTHON[0]}.{MAX_PYTHON[1]}"
        actual = f"{current_python[0]}.{current_python[1]}"
        raise SystemExit(
            f"Unsupported Python version for the frozen runtime: {actual}. "
            f"Use Python {supported}; CI uses Python 3.11."
        )

    problems = []
    for distribution, expected in EXPECTED_BUILD_DEPENDENCIES.items():
        try:
            actual = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            problems.append(f"{distribution} is not installed (required: {expected})")
            continue
        if actual != expected:
            problems.append(
                f"{distribution} {actual} is installed (required: {expected})"
            )

    if problems:
        details = "\n  - ".join(problems)
        raise SystemExit(
            "S-Lang frozen-runtime build dependencies are not ready:\n  - "
            f"{details}\nInstall the pinned dependencies with:\n"
            "  python -m pip install -r packaging/requirements-build.txt"
        )


def target_name() -> str:
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Windows":
        return "windows-x86_64"
    if system == "Darwin":
        return "macos-arm64" if machine in {"arm64", "aarch64"} else "macos-x64"
    if system == "Linux":
        return "linux-arm64" if machine in {"arm64", "aarch64"} else "linux-x86_64"
    raise SystemExit(f"Unsupported build platform: {system}/{machine}")


def find_compiler() -> str:
    candidates = ["clang", "gcc", "cc"]
    if platform.system() == "Windows":
        candidates = ["clang", "clang-cl"]
    for name in candidates:
        path = shutil.which(name)
        if path:
            return path
    raise SystemExit("No supported C compiler found on the runner")


def build_native_runtime() -> Path:
    compiler = find_compiler()
    system = platform.system()
    source = ROOT / "slang" / "slang_runtime.c"
    NATIVE_RUNTIME.mkdir(parents=True, exist_ok=True)

    if system == "Windows":
        output = NATIVE_RUNTIME / "slang_runtime.dll"
        command = [compiler, "-shared", "-O2", str(source), "-o", str(output)]
    elif system == "Darwin":
        output = NATIVE_RUNTIME / "libslang_runtime.dylib"
        command = [compiler, "-dynamiclib", "-O2", str(source), "-o", str(output)]
    else:
        output = NATIVE_RUNTIME / "libslang_runtime.so"
        command = [compiler, "-shared", "-fPIC", "-O2", str(source), "-o", str(output)]

    print("Building native runtime:", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)
    if not output.is_file():
        raise SystemExit(f"Native runtime was not produced: {output}")
    return output


def strip_llvmlite_linux() -> None:
    """Strip llvmlite's native LLVM library before PyInstaller bundles it."""
    if platform.system() != "Linux":
        return

    try:
        import llvmlite
    except ImportError as exc:
        raise SystemExit(
            "llvmlite is required for the Linux production runtime"
        ) from exc

    llvmlite_root = Path(llvmlite.__file__).resolve().parent

    libraries = sorted(
        path
        for path in llvmlite_root.rglob("libllvmlite.so")
        if path.is_file()
    )

    if not libraries:
        raise SystemExit(
            f"libllvmlite.so was not found under {llvmlite_root}"
        )

    strip = shutil.which("strip")
    if strip is None:
        raise SystemExit(
            "strip was not found on the Linux build runner"
        )

    for library in libraries:
        before = library.stat().st_size

        print()
        print("Stripping llvmlite:", library)
        print(f"Before: {before:,} bytes")

        subprocess.run(
            [strip, "--strip-unneeded", str(library)],
            cwd=ROOT,
            check=True,
        )

        after = library.stat().st_size

        print(f"After:  {after:,} bytes")
        print(f"Saved:  {before - after:,} bytes")

        if after >= before:
            print(
                "Warning: stripping did not reduce the library size"
            )


def native_runtime_for_current_platform() -> Path:
    """Return the platform runtime that must be embedded in the one-file app."""
    name = {
        "Windows": "slang_runtime.dll",
        "Darwin": "libslang_runtime.dylib",
        "Linux": "libslang_runtime.so",
    }.get(platform.system())
    if name is None:
        raise SystemExit(f"Unsupported native runtime platform: {platform.system()}")
    path = NATIVE_RUNTIME / name
    if not path.is_file():
        raise SystemExit(
            f"Native runtime library is missing: {path}. "
            "Build it before freezing the executable."
        )
    return path


def build_frozen_executable() -> Path:
    target = target_name()
    out = DIST / target
    out.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    native_runtime = native_runtime_for_current_platform()
    # PyInstaller uses a semicolon as the source/destination separator on Windows.
    binary_separator = ";" if platform.system() == "Windows" else ":"

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--onefile",
        "--console",
        "--name",
        ("slang1.0" if platform.system() == "Windows" else "slang"),
        "--distpath",
        str(out),
        "--workpath",
        str(BUILD),
        "--specpath",
        str(BUILD),
        "--paths",
        str(ROOT),

        # S-Lang package.
        "--collect-submodules",
        "slang",
        "--collect-data",
        "slang",

        # Native JIT.
        # Only the llvmlite binding layer is explicitly imported.
        "--hidden-import",
        "llvmlite",
        "--hidden-import",
        "llvmlite.binding",
        "--hidden-import",
        "llvmlite.binding.ffi",

        # Include the native LLVM library required by llvmlite.binding.
        "--collect-binaries",
        "llvmlite",

        # Embed the platform C ABI library inside the one-file executable.
        # The destination mirrors slang.native_jit._runtime_candidates().
        "--add-binary",
        f"{native_runtime}{binary_separator}slang/native_runtime",

        str(ENTRY),
    ]    
       

    # Explicitly preserve the native runtime as package data. The executable
    # itself can locate it through slang/native_runtime in the frozen tree.
    print("Building frozen executable for", target)
    subprocess.run(command, cwd=ROOT, check=True)

    exe = out / ("slang1.0.exe" if platform.system() == "Windows" else "slang")
    if not exe.is_file():
        raise SystemExit(f"PyInstaller completed without producing {exe}")
    if platform.system() != "Windows":
        exe.chmod(0o755)
    return exe


def smoke_test(executable: Path) -> None:
    print("Smoke test:", executable)
    result = subprocess.run(
        [str(executable), "version"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"S-Lang smoke test failed with exit code {result.returncode}")
    print(result.stdout.strip())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-smoke-test", action="store_true")
    args = parser.parse_args()

    check_build_dependencies()
    native = build_native_runtime()
    strip_llvmlite_linux()
    executable = build_frozen_executable()
    print(f"Built executable: {executable}")
    print(f"Bundled native runtime source artifact: {native}")
    if not args.skip_smoke_test:
        smoke_test(executable)


if __name__ == "__main__":
    main()
