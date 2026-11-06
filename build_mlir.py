#!/usr/bin/env python3
"""Build and run the real S-Lang MLIR -> LLVM pipeline when MLIR is installed."""
from __future__ import annotations
import argparse
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def exe(name: str, mlir_dir: str | None = None):
    candidates = []
    if mlir_dir:
        root = Path(mlir_dir)
        candidates += [root / "bin" / name, root.parent / "bin" / name]
    found = shutil.which(name)
    if found:
        candidates.append(Path(found))
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return str(candidate)
    raise SystemExit(f"error: required MLIR tool not found: {name}; set MLIR_DIR or PATH")

def toolchain_status(mlir_dir: str | None):
    tools = {name: None for name in ("mlir-opt", "mlir-translate", "clang")}
    for name in tools:
        if name == "clang":
            tools[name] = shutil.which(name) or shutil.which("gcc")
        else:
            try:
                tools[name] = exe(name, mlir_dir)
            except SystemExit:
                tools[name] = None
    return tools

def build_dialect(mlir_dir: str, jobs: int):
    build = ROOT / "mlir_build"
    build.mkdir(exist_ok=True)
    subprocess.run(["cmake", "-S", str(ROOT / "mlir_cpp"), "-B", str(build), f"-DMLIR_DIR={mlir_dir}"], check=True)
    subprocess.run(["cmake", "--build", str(build), "-j", str(jobs)], check=True)
    opt = build / "slang-opt"
    if not opt.exists():
        raise SystemExit(f"error: expected compiler not found: {opt}")
    return opt

def status(mlir_dir: str | None):
    tools = toolchain_status(mlir_dir)
    print("MLIR pipeline toolchain")
    print("mlir-opt = " + (tools["mlir-opt"] or "missing"))
    print("mlir-translate = " + (tools["mlir-translate"] or "missing"))
    print("clang = " + (tools["clang"] or "missing"))
    print("ready = " + ("yes" if all(tools.values()) else "no"))
    return 0 if all(tools.values()) else 1

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", nargs="?")
    ap.add_argument("-o", "--output", default=None)
    ap.add_argument("--mlir-dir", default=os.environ.get("MLIR_DIR"))
    ap.add_argument("-j", "--jobs", type=int, default=2)
    ap.add_argument("--keep-ir", action="store_true")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    if args.status:
        raise SystemExit(status(args.mlir_dir))
    if not args.source:
        ap.error("source is required unless --status is used")

    if not args.mlir_dir:
        raise SystemExit("error: MLIR_DIR is required; point it to the directory containing MLIRConfig.cmake")

    mlir_opt = exe("mlir-opt", args.mlir_dir)
    mlir_translate = exe("mlir-translate", args.mlir_dir)
    clang = shutil.which("clang") or shutil.which("gcc")
    if not clang:
        raise SystemExit("error: clang or gcc not found")

    slang_opt = build_dialect(args.mlir_dir, args.jobs)
    source = Path(args.source).resolve()
    output = Path(args.output).resolve() if args.output else source.with_suffix("")
    stage0 = ROOT / "mlir_build" / (source.stem + ".slang.mlir")
    stage1 = ROOT / "mlir_build" / (source.stem + ".lowered.mlir")
    stage2 = ROOT / "mlir_build" / (source.stem + ".llvm.mlir")
    ll = ROOT / "mlir_build" / (source.stem + ".ll")

    # Backend lowering is fed by the canonical semantic compiler pipeline.
    # The current out-of-tree MLIR backend supports physics.gravity only.
    from slang.core import parse, validate, slang_mlir
    from slang.backend import compile_for_backend
    p = parse(source.read_text(encoding="utf-8")); validate(p)
    compile_for_backend(p.ast, "mlir")
    stage0.write_text(slang_mlir(p), encoding="utf-8")

    with stage1.open("w", encoding="utf-8") as f:
        subprocess.run([str(slang_opt), str(stage0), "--lower-slang"], check=True, stdout=f)

    # Lower SCF/arith/index/func to LLVM dialect. Keep the external runtime call intact.
    passes = [
        "--convert-scf-to-cf",
        "--convert-arith-to-llvm",
        "--convert-index-to-llvm",
        "--convert-cf-to-llvm",
        "--convert-func-to-llvm",
        "--reconcile-unrealized-casts",
    ]
    with stage2.open("w", encoding="utf-8") as f:
        subprocess.run([mlir_opt, str(stage1), *passes], check=True, stdout=f)

    subprocess.run([mlir_translate, str(stage2), "--mlir-to-llvmir", "-o", str(ll)], check=True)
    runtime = ROOT / "runtime" / "slang_runtime.c"
    subprocess.run([clang, "-O2", "-x", "ir", str(ll), str(runtime), "-o", str(output)], check=True)

    if not args.keep_ir:
        for pth in (stage0, stage1, stage2, ll):
            pth.unlink(missing_ok=True)
    print(output)

if __name__ == "__main__":
    main()
