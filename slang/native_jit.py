"""In-process LLVM JIT used by S-Lang's self-contained native runtime.

The JIT executes the LLVM IR emitted by the existing native backend without
requiring clang/gcc at user runtime.  The platform runtime library is loaded
from the S-Lang installation and its exported ABI symbols are registered with
LLVM.
"""
from __future__ import annotations

import ctypes
import os
import re
from pathlib import Path
from typing import Iterable


def _runtime_candidates() -> Iterable[Path]:
    root = Path(__file__).resolve().parent
    package = root / "native_runtime"
    names = {
        "win32": ("slang_runtime.dll",),
        "darwin": ("libslang_runtime.dylib", "slang_runtime.dylib"),
    }.get(os.sys.platform, ("libslang_runtime.so",))
    for name in names:
        yield package / name
        yield root.parent / "runtime" / name


def _load_runtime():
    for path in _runtime_candidates():
        if path.is_file():
            return ctypes.CDLL(str(path))
    return None


def _register_library_symbols(lib) -> set[str]:
    registered: set[str] = set()
    if lib is None:
        return registered
    from llvmlite import binding
    # Register every exported slang_* ABI symbol that exists in the bundled
    # runtime.  Missing optional symbols are harmless.
    names = (
        "slang_print_result", "slang_reduce_f64",
        "slang_number_list_new", "slang_number_list_set",
        "slang_number_list_count", "slang_number_list_item", "slang_number_list_free",
        "slang_file_exists", "slang_file_size", "slang_is_file",
        "slang_is_directory", "slang_file_write", "slang_file_read",
        "slang_text_trim", "slang_text_lower", "slang_text_upper",
        "slang_text_starts_with", "slang_text_ends_with", "slang_text_replace",
        "slang_text_free", "slang_text_split", "slang_file_read_lines",
        "slang_text_list_count", "slang_text_list_item", "slang_text_list_free",
        "slang_file_write_lines", "slang_path_basename", "slang_path_dirname",
        "slang_path_extension", "slang_path_join", "slang_path_normalize",
        "slang_make_directory", "slang_remove_directory", "slang_file_list_directory",
        "slang_process_arguments", "slang_process_run", "slang_process_run_program",
        "slang_process_run_program_env", "slang_process_environment",
        # CSV ABI used by specialized native lowering paths.
        "slang_csv_open", "slang_csv_field_index", "slang_csv_sort_print",
        "slang_csv_free", "slang_csv_count", "slang_csv_get_text",
    )
    for name in names:
        try:
            address = ctypes.cast(getattr(lib, name), ctypes.c_void_p).value
        except AttributeError:
            continue
        if address:
            binding.add_symbol(name, address)
            registered.add(name)
    return registered


def execute_llvm(ir_text: str, function: str = "main") -> int:
    """JIT-compile and execute LLVM IR in the current process."""
    try:
        from llvmlite import binding
    except ImportError as exc:
        raise RuntimeError(
            "native JIT support is not included in this S-Lang runtime build"
        ) from exc

    binding.initialize_native_target()
    binding.initialize_native_asmprinter()

    # Resolve standard C functions used by generated IR.
    process = ctypes.CDLL(None)
    for name in ("printf", "fprintf", "puts", "malloc", "calloc", "realloc", "free", "memcpy", "strlen"):
        try:
            binding.add_symbol(name, ctypes.cast(getattr(process, name), ctypes.c_void_p).value)
        except AttributeError:
            pass
    runtime_symbols = _register_library_symbols(_load_runtime())

    # MCJIT can otherwise accept calls to unresolved runtime symbols and crash
    # the whole Python process when the generated function is invoked. Detect
    # S-Lang ABI calls before compilation and report a controlled error instead.
    called_runtime_symbols = set(re.findall(r"\bcall\b[^\n]*?@((?:slang_)[A-Za-z0-9_]+)\s*\(", ir_text))
    missing_runtime_symbols = sorted(called_runtime_symbols - runtime_symbols)
    if missing_runtime_symbols:
        missing = ", ".join(missing_runtime_symbols)
        raise RuntimeError(
            "native JIT program requires runtime symbols unavailable in this build: "
            f"{missing}. Install a runtime build that includes the matching slang_runtime library."
        )

    module = binding.parse_assembly(ir_text)
    module.verify()
    target = binding.Target.from_default_triple()
    machine = target.create_target_machine()
    engine = binding.create_mcjit_compiler(binding.parse_assembly(""), machine)
    engine.add_module(module)
    engine.finalize_object()
    engine.run_static_constructors()
    address = engine.get_function_address(function)
    if not address:
        raise RuntimeError(f"native JIT function '{function}' was not emitted")
    fn = ctypes.CFUNCTYPE(ctypes.c_int)(address)
    return int(fn())
