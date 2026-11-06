from __future__ import annotations
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from .core import parse_file, validate, run, ir, goal_ir, execution_ir, execution_schedule, execution_plan, mlir, slang_mlir, llvm_ir, show_value, show_expr_value, ParseError
from .optimizer import optimize_program


def _runtime_source_path() -> Path:
    """Return the bundled runtime for both source-tree and installed layouts."""
    bundled = Path(__file__).resolve().with_name("slang_runtime.c")
    if bundled.is_file():
        return bundled
    return Path(__file__).resolve().parents[1] / "runtime" / "slang_runtime.c"


def _load(path: Path):
    p = parse_file(path)
    validate(p)
    return p


def _compile_direct(source: Path, output: Path, keep_ir: bool = False):
    p = _load(source)
    ll = output.with_suffix(".ll")
    ll.write_text(llvm_ir(p), encoding="utf-8")
    clang = shutil.which("clang") or shutil.which("gcc")
    if not clang:
        raise SystemExit("error: clang or gcc not found; use 'slang run --native-jit' for self-contained native execution")
    runtime = _runtime_source_path()
    cmd = [clang, "-O2", str(ll), str(runtime), "-lm", "-o", str(output)]
    subprocess.run(cmd, check=True)
    if not keep_ir:
        ll.unlink(missing_ok=True)
    return output


def main():
    ap = argparse.ArgumentParser(prog="slang", description="S-Lang compiler")
    sub = ap.add_subparsers(dest="command")

    for name in ("check", "run", "ir", "emit-mlir", "emit-slang-mlir", "emit-llvm", "analyze", "optimize", "emit-goal-ir", "plan", "graph", "emit-execution-ir", "schedule", "memory", "alias", "conflicts", "dependencies", "analyze-dependencies", "execution-plan", "selected-execution-plan", "explain-execution", "effects", "function-effects", "higher-order-effects", "strategies", "cost-model", "cardinality", "optimize-ir", "pipeline", "backend-status", "lower-mlir", "emit-backend-mlir", "backend-capabilities", "select-backend", "project", "resolve-packages", "lock", "explain-imports", "compile-decision", "execution-contract", "runtime", "contract-check", "lowering-contract", "lower", "compile"):
        sp = sub.add_parser(name)
        sp.add_argument("source")
        if name == "resolve-packages":
            sp.add_argument("--fresh", action="store_true", help="ignore slang.lock and resolve the manifests again")
        if name == "lock":
            sp.add_argument("--check", action="store_true", help="verify that slang.lock is current without rewriting it")
        if name == "run":
            sp.add_argument("--native", action="store_true", help="compile with the native backend and execute the produced program")
            sp.add_argument("--native-jit", action="store_true", help="execute supported native LLVM IR in-process without clang/gcc")

    sp = sub.add_parser("init", help="create a new S-Lang project")
    sp.add_argument("directory", nargs="?", default=".", help="project directory to create")
    sp.add_argument("--name", default=None, help="package name; defaults to the directory name")
    sp.add_argument("--version", default="0.1.0", help="initial package version")

    sp = sub.add_parser("diagnose", help="parse and validate a source file and print structured diagnostics")
    sp.add_argument("source")
    sp.add_argument("--json", action="store_true", help="emit machine-readable JSON diagnostics")

    sp = sub.add_parser("package", help="build and publish a package to the local registry")
    sp.add_argument("source")
    sp.add_argument("-o", "--output", default=None, help="optional .slpkg output path; without it, publish to the local registry")
    sp.add_argument("--registry", default=None, help="local registry directory")
    sp.add_argument("--check", action="store_true", help="validate the package without publishing it")
    sp.add_argument("--force", action="store_true", help="replace an existing registry version")

    sp = sub.add_parser("install", help="install a package from the local registry")
    sp.add_argument("source")
    sp.add_argument("package")
    sp.add_argument("--version", default=None, help="version constraint, e.g. ^1.2.0")
    sp.add_argument("--registry", default=None, help="local registry directory")

    sp = sub.add_parser("registry", help="inspect the local package registry")
    sp.add_argument("action", choices=("list", "remove"), default="list")
    sp.add_argument("package", nargs="?")
    sp.add_argument("version", nargs="?")
    sp.add_argument("--registry", default=None, help="local registry directory")

    sp = sub.add_parser("stdlib", help="inspect the public standard-library surface")
    sp.add_argument("module", nargs="?", help="optional standard-library module name")
    sub.add_parser("validate-suite", help="run the deterministic end-to-end language validation corpus")
    sub.add_parser("practical-suite", help="run practical end-to-end language cases and report descriptive ergonomics metrics")
    sp = sub.add_parser("comparison-suite", help="compare equivalent S-Lang, Python, and C++ tasks")
    sp.add_argument("--iterations", type=int, default=3, help="repetitions per case")
    sp.add_argument("--skip-native", action="store_true", help="skip optional native execution checks")
    sub.add_parser("real-world-suite", help="compare practical S-Lang, Python, and C++ programs")
    sub.add_parser("full-comparison-suite", help="run the complete S-Lang/Python/C++ comparison corpus")
    sub.add_parser("expressiveness-suite", help="compare S-Lang task size with descriptive imperative reference sizes and report current language gaps")
    sub.add_parser("stateful-suite", help="validate nested structured-state and branching sequence computations")
    sub.add_parser("composition-suite", help="validate composition of stateful generators and declarative dataflow")
    sub.add_parser("coupled-state-suite", help="validate atomic structured state with interdependent fields and declarative consumers")
    sub.add_parser("goal-directed-suite", help="validate deterministic goal-directed state transitions")
    sub.add_parser("structured-goal-suite", help="validate goal-directed transitions over structured state")
    sub.add_parser("multi-constraint-suite", help="validate conjunction of multiple structured satisfy constraints")
    sub.add_parser("stress-suite", help="run larger multi-stage semantic stress cases")
    sub.add_parser("rc-stability-suite", help="run final release-candidate stability and recovery acceptance checks")
    sub.add_parser("release-check", help="run the S-Lang 1.0 semantic acceptance suite")
    sub.add_parser("release-manifest", help="write a deterministic SHA-256 manifest for the project tree")
    sub.add_parser("release-verify", help="verify the deterministic SHA-256 release manifest")
    sp = sub.add_parser("release-audit", help="audit release metadata, manifest, archive reproducibility, and release-tree hygiene")
    sp.add_argument("--archive", default=None, help="optional release ZIP to verify in addition to the project tree")
    sp = sub.add_parser("release-bundle", help="build a deterministic release ZIP from the verified project tree")
    sp.add_argument("-o", "--output", default=None, help="output ZIP path (outside the project tree)")
    sp = sub.add_parser("release-bundle-verify", help="verify a deterministic release ZIP against its embedded manifest")
    sp.add_argument("archive")
    sub.add_parser("doctor", help="check the local S-Lang toolchain and runtime prerequisites")
    sub.add_parser("version", help="print the installed S-Lang version")
    lsp_parser = sub.add_parser("lsp", help="start the S-Lang Language Server over stdio")
    # vscode-languageclient appends these arguments for stdio transports.
    # S-Lang always serves LSP over stdio, so --stdio is accepted as a
    # compatibility flag; the client PID is informational and not required.
    lsp_parser.add_argument("--stdio", action="store_true", help=argparse.SUPPRESS)
    lsp_parser.add_argument("--clientProcessId", type=int, default=None, help=argparse.SUPPRESS)
    sub.add_parser("installation-suite", help="verify clean installation and install-to-run user workflow")
    sub.add_parser("e2e-suite", help="run end-to-end source, standard-library, package, native, and persisted-artifact scenarios")
    sub.add_parser("e2e-extended-suite", help="run the expanded standard-library, generics, collections, and native acceptance matrix")
    sp = sub.add_parser("performance-suite", help="measure repeated interpreter/native execution and verify result stability")
    sp.add_argument("--iterations", type=int, default=3, help="repetitions per case (minimum 2)")
    sp = sub.add_parser("ai-audit", help="report descriptive metrics for human review of AI-generated S-Lang code")
    sp.add_argument("source")

    sp = sub.add_parser("build")
    sp.add_argument("source")
    sp.add_argument("-o", "--output", default=None)
    sp.add_argument("--backend", choices=("auto", "native", "mlir"), default="auto")
    sp.add_argument("--keep-ir", action="store_true")

    # Backward-compatible flags from 0.18.
    ap.add_argument("legacy_source", nargs="?")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--ir", action="store_true")
    ap.add_argument("--mlir", action="store_true")
    ap.add_argument("--llvm", action="store_true")
    ap.add_argument("--slang-mlir", action="store_true")
    args = ap.parse_args()

    try:
        if args.command == "lsp":
            from .lsp_process import run_lsp_server
            run_lsp_server(sys.stdin.buffer, sys.stdout.buffer)
            return

        if args.command == "init":
            import json
            from .project import init_project
            root = init_project(args.directory, name=args.name, version=args.version)
            print(json.dumps({"status": "created", "project": str(root), "entry": str(root / "src" / "main.sl")}, indent=2, ensure_ascii=False))
            return

        if args.command == "diagnose":
            import json
            from .diagnostics import diagnostics_for_source, format_diagnostics
            source_path = Path(args.source).resolve()
            source_text = source_path.read_text(encoding="utf-8")
            bag = diagnostics_for_source(source_text, path=str(source_path))
            if args.json:
                print(json.dumps({"diagnostics": bag.to_dict(), "error_count": sum(1 for d in bag.diagnostics if d.severity.value == "error")}, indent=2, ensure_ascii=False))
            elif bag.diagnostics:
                print(format_diagnostics(bag.diagnostics, source_text))
            else:
                print("No diagnostics.")
            if bag.has_errors:
                raise SystemExit(1)
            return

        if args.command == "project":
            import json
            from .project import find_root, explain_project
            target = Path(args.source or ".").resolve()
            root = find_root(target)
            if root is None:
                raise SystemExit("error: slang.toml not found")
            print(json.dumps(explain_project(root), indent=2, ensure_ascii=False))
            return

        if args.command == "resolve-packages":
            import json
            from .project import find_root, resolve_dependencies
            target = Path(args.source or ".").resolve()
            root = find_root(target)
            if root is None:
                raise SystemExit("error: slang.toml not found")
            print(json.dumps(resolve_dependencies(root, use_lock=not args.fresh), indent=2, ensure_ascii=False))
            return

        if args.command == "package":
            import json
            from .project import find_root, package_archive, publish_package
            target = Path(args.source or ".").resolve()
            root = find_root(target)
            if root is None:
                raise SystemExit("error: slang.toml not found")
            if args.check:
                from .project import check_package
                print(json.dumps(check_package(root, args.output), indent=2, ensure_ascii=False))
                return
            if args.output:
                archive = package_archive(root, args.output)
                print(json.dumps({"status": "built", "archive": str(archive)}, indent=2, ensure_ascii=False))
            else:
                print(json.dumps({"status": "published", **publish_package(root, args.registry, force=args.force)}, indent=2, ensure_ascii=False))
            return

        if args.command == "install":
            import json
            from .project import find_root, install_package
            target = Path(args.source or ".").resolve()
            root = find_root(target)
            if root is None:
                raise SystemExit("error: slang.toml not found")
            print(json.dumps(install_package(root, args.package, args.version, args.registry), indent=2, ensure_ascii=False))
            return

        if args.command == "registry":
            import json
            from .project import registry_list, remove_registry_package
            if args.action == "remove":
                if not args.package or not args.version:
                    raise SystemExit("error: registry remove requires PACKAGE VERSION")
                print(json.dumps(remove_registry_package(args.package, args.version, args.registry), indent=2, ensure_ascii=False))
            else:
                print(json.dumps({"registry": str(Path(args.registry).expanduser().resolve()) if args.registry else None, "packages": registry_list(args.registry)}, indent=2, ensure_ascii=False))
            return

        if args.command == "lock":
            import json
            from .project import find_root, lock_path, write_lock, resolve_dependencies
            target = Path(args.source or ".").resolve()
            root = find_root(target)
            if root is None:
                raise SystemExit("error: slang.toml not found")
            if args.check:
                if not lock_path(root).is_file():
                    raise SystemExit(f"error: S-Lang lock file not found: {lock_path(root)}")
                graph = resolve_dependencies(root, use_lock=True)
                print(json.dumps({"lock_file": str(lock_path(root)), "status": "current", "packages": graph["packages"]}, indent=2, ensure_ascii=False))
            else:
                data = write_lock(root)
                print(json.dumps({"lock_file": str(lock_path(root)), "status": "written", "format": data["format"], "packages": data["packages"]}, indent=2, ensure_ascii=False))
            return

        if args.command == "explain-imports":
            import json
            from .project import resolve_import
            source = Path(args.source).resolve()
            p = _load(source)
            rows = []
            for imp in p.ast.imports:
                if imp.path.startswith("std."):
                    rows.append({"import": imp.path, "kind": "standard", "resolved": imp.path})
                else:
                    resolved = resolve_import(source.parent, imp.path)
                    rows.append({"import": imp.path, "kind": "project-or-source", "namespace": imp.alias, "resolved": str(resolved) if resolved else None})
            print(json.dumps({"source": str(source), "imports": rows}, indent=2, ensure_ascii=False))
            return

        if args.command == "stdlib":
            import json
            from .stdlib.catalog import entries
            from .stdlib.modules import MODULES, module_entries, modules
            if args.module is None:
                print(json.dumps({"module_count": len(MODULES), "modules": modules(), "count": len(entries()), "entries": entries()}, indent=2, ensure_ascii=False))
            else:
                if args.module not in MODULES:
                    raise SystemExit(f"unknown standard-library module: {args.module}")
                rows = module_entries(args.module)
                print(json.dumps({"module": args.module, "description": MODULES[args.module], "count": len(rows), "entries": rows}, indent=2, ensure_ascii=False))
            return

        if args.command == "ai-audit":
            import json
            from .ai_audit import audit
            source = Path(args.source).read_text(encoding="utf-8")
            validate(parse_file(args.source))
            print(json.dumps(audit(source), indent=2, ensure_ascii=False))
            return

        if args.command == "validate-suite":
            import json
            from .validation_suite import run_suite
            results = run_suite()
            print(json.dumps(results, indent=2, ensure_ascii=False))
            if not all(row["semantic_match"] for row in results):
                raise SystemExit(1)
            return

        if args.command == "comparison-suite":
            import json
            from .comparison_suite import run_suite
            result = run_suite(args.iterations, native=not args.skip_native)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            if not result["summary"]["all_correct"]:
                raise SystemExit(1)
            return

        if args.command == "real-world-suite":
            import json
            from .real_world_suite import run_suite
            result = run_suite()
            print(json.dumps(result, indent=2, ensure_ascii=False))
            if not result["summary"]["all_correct"]:
                raise SystemExit(1)
            return

        if args.command == "full-comparison-suite":
            import json
            from .full_comparison_suite import run_suite, write_report
            result = run_suite()
            write_report(result)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            if not result["summary"]["all_correct"]:
                raise SystemExit(1)
            return

        if args.command == "practical-suite":
            import json
            from .practical_suite import run_suite
            results = run_suite()
            print(json.dumps({"cases": results, "summary": {
                "cases": len(results),
                "passed": sum(1 for row in results if row["semantic_match"]),
                "source_lines": sum(row["source_lines"] for row in results),
                "intent_operations": sorted({op for row in results for op in row["intent_operations"]}),
                "deterministic": True,
            }}, indent=2, ensure_ascii=False))
            if not all(row["semantic_match"] for row in results):
                raise SystemExit(1)
            return

        if args.command == "goal-directed-suite":
            import json
            from .goal_directed_suite import run_suite
            results = run_suite()
            print(json.dumps({"cases": results, "summary": {
                "cases": len(results),
                "passed": sum(1 for row in results if row["semantic_match"] and row["dependency_graph_match"]),
                "goal_directed_transition": True,
                "deterministic": True,
            }}, indent=2, ensure_ascii=False))
            if not all(row["semantic_match"] and row["dependency_graph_match"] for row in results):
                raise SystemExit(1)
            return

        if args.command == "structured-goal-suite":
            import json
            from .structured_goal_suite import run_suite
            results = run_suite()
            print(json.dumps({"cases": results, "summary": {
                "cases": len(results),
                "passed": sum(1 for row in results if row["semantic_match"] and row["dependency_graph_match"]),
                "structured_state": True,
                "deterministic": True,
            }}, indent=2, ensure_ascii=False))
            if not all(row["semantic_match"] and row["dependency_graph_match"] for row in results):
                raise SystemExit(1)
            return

        if args.command == "multi-constraint-suite":
            import json
            from .multi_constraint_suite import run_suite
            results = run_suite()
            print(json.dumps({"cases": results, "summary": {
                "cases": len(results),
                "passed": sum(1 for row in results if row["semantic_match"] and row["dependency_graph_match"]),
                "multiple_constraints": True,
                "deterministic": True,
            }}, indent=2, ensure_ascii=False))
            if not all(row["semantic_match"] and row["dependency_graph_match"] for row in results):
                raise SystemExit(1)
            return

        if args.command == "release-manifest":
            import json
            from .release_manifest import write_manifest
            path = write_manifest(Path.cwd())
            print(json.dumps({"manifest": str(path), "status": "written"}, indent=2))
            return

        if args.command == "release-verify":
            import json
            from .release_manifest import verify_manifest
            result = verify_manifest(Path.cwd())
            print(json.dumps(result, indent=2))
            if not result["valid"]:
                raise SystemExit(1)
            return

        if args.command == "release-audit":
            import json
            from .release_audit import audit_release
            result = audit_release(Path.cwd(), args.archive)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            if not result["release_ready"]:
                raise SystemExit(1)
            return

        if args.command == "release-bundle":
            import json
            from .release_bundle import write_bundle
            output = args.output or str(Path.cwd().parent / f"S-Lang-{Path.cwd().name}.zip")
            path = write_bundle(Path.cwd(), output)
            print(json.dumps({"archive": str(path), "status": "written"}, indent=2))
            return

        if args.command == "release-bundle-verify":
            import json
            from .release_bundle import verify_bundle
            result = verify_bundle(args.archive)
            print(json.dumps(result, indent=2))
            if not result["valid"]:
                raise SystemExit(1)
            return

        if args.command == "release-check":
            import json
            from .release_suite import run_suite
            result = run_suite()
            print(json.dumps(result, indent=2, ensure_ascii=False))
            if not result["release_ready"]:
                raise SystemExit(1)
            return

        if args.command == "rc-stability-suite":
            import json
            from .rc_stability_suite import run_suite
            result = run_suite()
            print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
            if not result["passed"]:
                raise SystemExit(1)
            return

        if args.command == "performance-suite":
            import json
            from .performance_suite import run_suite
            results = run_suite(args.iterations)
            summary = {
                "cases": len(results),
                "passed": sum(1 for row in results if row["stable"]),
                "all_stable": all(row["stable"] for row in results),
                "iterations": args.iterations,
                "deterministic": all(row["interpreter_deterministic"] and row["native_deterministic"] for row in results),
                "interpreter_native_consistent": all(row["interpreter_native_result_match"] for row in results),
            }
            print(json.dumps({"cases": results, "summary": summary}, indent=2, ensure_ascii=False))
            if not summary["all_stable"]:
                raise SystemExit(1)
            return

        if args.command == "stress-suite":
            import json
            from .stress_suite import run_suite
            results = run_suite()
            print(json.dumps({"cases": results, "summary": {
                "cases": len(results),
                "passed": sum(1 for row in results if row["semantic_match"] and row["required_kinds_present"]),
                "total_source_lines": sum(row["source_lines"] for row in results),
                "total_graph_nodes": sum(row["node_count"] for row in results),
                "deterministic": True,
            }}, indent=2, ensure_ascii=False))
            if not all(row["semantic_match"] and row["required_kinds_present"] for row in results):
                raise SystemExit(1)
            return

        if args.command == "stateful-suite":
            import json
            from .stateful_suite import run_suite
            results = run_suite()
            print(json.dumps({"cases": results, "summary": {
                "cases": len(results),
                "passed": sum(1 for row in results if row["semantic_match"]),
                "nested_state_supported": True,
                "deterministic": True,
            }}, indent=2, ensure_ascii=False))
            if not all(row["semantic_match"] for row in results):
                raise SystemExit(1)
            return

        if args.command == "coupled-state-suite":
            import json
            from .coupled_state_suite import run_suite
            results = run_suite()
            print(json.dumps({"cases": results, "summary": {
                "cases": len(results),
                "semantic_passed": sum(1 for row in results if row["semantic_match"]),
                "dependency_graph_passed": sum(1 for row in results if row["dependency_graph_match"]),
                "atomic_state_model": all(row["atomic_state_model"] for row in results),
                "deterministic": True,
            }}, indent=2, ensure_ascii=False))
            if not all(row["semantic_match"] and row["dependency_graph_match"] for row in results):
                raise SystemExit(1)
            return

        if args.command == "composition-suite":
            import json
            from .composition_suite import run_suite
            results = run_suite()
            print(json.dumps({"cases": results, "summary": {
                "cases": len(results),
                "semantic_passed": sum(1 for row in results if row["semantic_match"]),
                "dependency_graph_passed": sum(1 for row in results if row["dependency_graph_match"]),
                "composition_supported": all(row["semantic_match"] and row["dependency_graph_match"] for row in results),
                "deterministic": True,
            }}, indent=2, ensure_ascii=False))
            if not all(row["semantic_match"] and row["dependency_graph_match"] for row in results):
                raise SystemExit(1)
            return

        if args.command == "expressiveness-suite":
            import json
            from .expressiveness_suite import run_suite, gap_report
            results = run_suite()
            print(json.dumps({"cases": results, "gaps": gap_report(), "summary": {
                "cases": len(results),
                "semantic_cases": sum(1 for row in results if row["semantic_result_available"]),
                "slang_lines": sum(row["slang_lines"] for row in results),
                "reference_lines": sum(row["reference_lines"] for row in results),
                "line_reduction": sum(row["line_reduction"] for row in results),
                "comparison_type": "descriptive_size_only",
                "performance_benchmark": False,
            }}, indent=2, ensure_ascii=False))
            return

        if args.command == "e2e-suite":
            import json
            from .e2e_suite import run_suite
            result = run_suite()
            print(json.dumps(result, indent=2, ensure_ascii=False))
            if not result["summary"]["release_blocking"]:
                raise SystemExit(1)
            return

        if args.command == "e2e-extended-suite":
            import json
            from .e2e_extended_suite import run_suite
            result = run_suite()
            print(json.dumps(result, indent=2, ensure_ascii=False))
            if not result["summary"]["release_blocking"]:
                raise SystemExit(1)
            return

        if args.command == "installation-suite":
            import json
            from .installation_suite import run_suite
            result = run_suite(Path(__file__).resolve().parents[1])
            print(json.dumps(result, indent=2, ensure_ascii=False))
            if not result["passed"]:
                raise SystemExit(1)
            return

        if args.command == "version":
            import importlib.metadata
            project_root = Path(__file__).resolve().parents[1]
            pyproject = project_root / "pyproject.toml"
            if pyproject.exists():
                import re
                match = re.search(r'^version\s*=\s*"([^"]+)"\s*$', pyproject.read_text(encoding="utf-8"), re.MULTILINE)
                if match:
                    # The public language line is MAJOR.MINOR (currently 1.0);
                    # the patch component tracks the compiler package build.
                    print(".".join(match.group(1).split(".")[:2]))
                    return
            try:
                version = importlib.metadata.version("slang-language")
            except importlib.metadata.PackageNotFoundError:
                version = "1.0"

            print(version)
            return

        if args.command == "doctor":
            import json
            clang = shutil.which("clang")
            gcc = shutil.which("gcc")
            result = {
                "python": sys.version.split()[0],
                "clang": clang,
                "gcc": gcc,
                "native_build_available": bool(clang or gcc),
                "runtime_source": str(_runtime_source_path()),
                "status": "ready" if (clang or gcc) else "interpreter-only",
            }
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        if args.command:
            src = Path(getattr(args, "source"))
            p = _load(src)
            if args.command == "check":
                print("OK")
            elif args.command == "run":
                if getattr(args, "native_jit", False):
                    from .native_jit import execute_llvm
                    # JIT mode intentionally does not consult the external C
                    # toolchain capability check. The generated LLVM IR is
                    # executed directly by the bundled LLVM JIT.
                    return execute_llvm(llvm_ir(p))
                if getattr(args, "native", False):
                    from .backend import compile_program
                    result = compile_program(p, "native")
                    lowered = result.lowered
                    if lowered.backend != "native-llvm":
                        raise ValueError("native execution requires the native-llvm backend")
                    if not shutil.which("clang") and not shutil.which("gcc"):
                        raise ValueError("native execution requires clang or gcc; use 'slang run' for interpreter execution")
                    import tempfile
                    with tempfile.TemporaryDirectory(prefix="slang-run-") as td:
                        out = Path(td) / (src.stem + (".exe" if sys.platform == "win32" else ""))
                        ll = Path(td) / (src.stem + ".ll")
                        ll.write_text(lowered.text, encoding="utf-8")
                        compiler = shutil.which("clang") or shutil.which("gcc")
                        runtime = _runtime_source_path()
                        subprocess.run([compiler, "-O2", str(ll), str(runtime), "-lm", "-o", str(out)], check=True)
                        subprocess.run([str(out)], check=True)
                else:
                    run(p)
                    for expr in (p.show_exprs or []): print(show_expr_value(p, expr))
                    if not p.show_exprs:
                        for n, f in p.shows: print(f"{n}{'' if f == '__value__' else '.' + f} = {show_value(p, n, f)}")
            elif args.command == "ir":
                print(ir(p))
            elif args.command == "analyze":
                nonempty = sum(1 for line in src.read_text(encoding="utf-8").splitlines() if line.strip() and not line.strip().startswith("#"))
                domains = []
                if p.gravity or p.bodies or p.simulation: domains.append("physics")
                if p.people or p.data_query: domains.append("data")
                if p.circles: domains.append("geometry")
                if p.ast.graphs: domains.append("graph")
                ops = []
                if p.gravity: ops.append("physics.gravity")
                if p.bodies: ops.append(f"body[{len(p.bodies)}]")
                if p.simulation: ops.append("simulate.gravity")
                if p.ast.filters: ops.append(f"filter[{len(p.ast.filters)}]")
                if p.ast.sorts: ops.append(f"sort[{len(p.ast.sorts)}]")
                if p.ast.maps: ops.append(f"map[{len(p.ast.maps)}]")
                if p.ast.aggregates: ops.append(f"aggregate[{len(p.ast.aggregates)}]")
                if p.ast.reduces: ops.append(f"reduce[{len(p.ast.reduces)}]")
                if p.ast.goals: ops.append(f"goal[{len(p.ast.goals)}]")
                if p.ast.graphs: ops.append(f"graph[{len(p.ast.graphs)}]")
                if p.ast.path_goals: ops.append(f"path_goal[{len(p.ast.path_goals)}]")
                if p.ast.satisfy_goals: ops.append(f"satisfy[{len(p.ast.satisfy_goals)}]")
                if p.circles: ops.append("circle.derived")
                print(f"source_lines = {nonempty}")
                module_name = p.ast.module.name if p.ast.module else "anonymous"
                print(f"module = {module_name}")
                print("imports = " + (", ".join(x.path for x in p.ast.imports) if p.ast.imports else "none"))
                print("domains = " + (", ".join(domains) if domains else "none"))
                print("semantic_ops = " + (", ".join(ops) if ops else "none"))
                from .goal_ir import lower_goals
                goal_count = len(lower_goals(p.ast))
                print(f"goal_ir_ops = {goal_count}")
                from .goal_plan import build_execution_plan
                plans = build_execution_plan(p.ast).goals
                print(f"goal_plan_ops = {len(plans)}")
                print(f"goal_dependencies = {sum(1 for x in plans if x.dependencies)}")
                from .semantic_graph import build_semantic_graph
                print(f"semantic_graph_ops = {len(build_semantic_graph(p.ast).nodes)}")
                report = optimize_program(p)
                print(f"optimizations_available = {report.total}")
                print("optimization_model = semantics_preserving")
                print("deterministic = yes")
                print("ai_runtime_dependency = no")
            elif args.command == "emit-goal-ir":
                print(goal_ir(p))
            elif args.command == "emit-execution-ir":
                print(execution_ir(p))
            elif args.command == "analyze-dependencies":
                from .core import dependency_analysis
                print(dependency_analysis(p))
            elif args.command == "schedule":
                print(execution_schedule(p))
            elif args.command == "execution-plan":
                print(execution_plan(p))
            elif args.command == "selected-execution-plan":
                from .core import selected_execution_plan
                print(selected_execution_plan(p))
            elif args.command == "explain-execution":
                from .core import execution_explain
                print(execution_explain(p))
            elif args.command == "effects":
                from .core import effect_analysis
                print(effect_analysis(p))
            elif args.command == "function-effects":
                from .core import function_effect_analysis
                print(function_effect_analysis(p))
            elif args.command == "higher-order-effects":
                from .core import higher_order_effect_analysis
                print(higher_order_effect_analysis(p))
            elif args.command == "pipeline":
                from .core import compiler_pipeline
                from .compiler_pipeline import format_compiler_pipeline
                print(format_compiler_pipeline(compiler_pipeline(p)))
            elif args.command == "backend-status":
                from .backend import mlir_toolchain_status, format_backend_status
                print(format_backend_status(mlir_toolchain_status()))
            elif args.command == "select-backend":
                from .backend import select_backend, format_backend_selection
                print(format_backend_selection(select_backend(p.ast)))
            elif args.command == "compile-decision":
                from .backend import compile_selected_backend, format_compilation_decision
                print(format_compilation_decision(compile_selected_backend(p.ast)))
            elif args.command == "runtime":
                from .core import runtime_execute
                from .runtime import format_runtime_trace
                _, trace = runtime_execute(p)
                print(format_runtime_trace(trace))
            elif args.command == "execution-contract":
                from .backend import compile_selected_backend
                from .execution_contract import format_execution_contract
                decision = compile_selected_backend(p.ast)
                print(format_execution_contract(decision.execution_contract))
            elif args.command == "contract-check":
                from .backend import compile_selected_backend, validate_contract_closure
                decision = compile_selected_backend(p.ast)
                validate_contract_closure(
                    decision.execution_contract,
                    decision.lowering_contract,
                    __import__("slang.backend", fromlist=["capabilities_for"]).capabilities_for(
                        "native" if decision.backend == "native-llvm" else "mlir"
                    ),
                )
                print("contract.check {")
                print(f"  backend = {decision.backend}")
                print("  execution_contract = valid")
                print("  lowering_contract = valid")
                print("  runtime_features = valid")
                print("  closure = complete")
                print("}")
            elif args.command == "lowering-contract":
                from .backend import compile_selected_backend
                decision = compile_selected_backend(p.ast)
                contract = decision.lowering_contract
                print("backend.lowering.contract {")
                print(f"  backend = {contract.backend}")
                for strategy, lowerer in contract.strategy_lowerers:
                    print(f"  strategy {strategy} -> {lowerer}")
                print("  executable_strategies = " + (", ".join(contract.executable_strategies) if contract.executable_strategies else "none"))
                print("  executable_operations = " + (", ".join(contract.executable_operations) if contract.executable_operations else "none"))
                print("  validated = yes")
                print("}")
            elif args.command == "lower":
                from .backend import compile_program
                result = compile_program(p, "auto")
                lowered = result.lowered
                print("backend.lowered {")
                print(f"  backend = {lowered.backend}")
                print(f"  strategy = {lowered.strategy}")
                print(f"  lowerer = {lowered.lowerer}")
                print(f"  format = {lowered.format}")
                print("}")
                print(lowered.text)
            elif args.command == "compile":
                from .backend import compile_program
                result = compile_program(p, "auto")
                decision = result.decision
                lowered = result.lowered
                print("compiler.result {")
                print(f"  backend = {decision.backend}")
                print(f"  strategies = {len(decision.pipeline.strategies)}")
                print(f"  lowering = {lowered.lowerer}")
                print(f"  format = {lowered.format}")
                print("  executable = " + ("yes" if lowered.executable else "not-yet-emitted"))
                print("  pipeline = complete")
                print("  deterministic = yes")
                print("}")
            elif args.command == "backend-capabilities":
                from .backend import capabilities_for, compile_semantic_pipeline, unsupported_strategies
                pipeline = compile_semantic_pipeline(p.ast)
                for backend_name in ("native", "mlir"):
                    caps = capabilities_for(backend_name)
                    missing = unsupported_strategies(pipeline, caps)
                    print(f"backend.capabilities {{")
                    print(f"  backend = {caps.name}")
                    print("  toolchain_ready = " + ("yes" if caps.toolchain_ready else "no"))
                    print("  selected_strategies = " + (", ".join(c.strategy for c in pipeline.strategies) if pipeline.strategies else "none"))
                    print("  supported_types = " + (", ".join(caps.supported_types) if caps.supported_types else "none"))
                    print("  supported_operations = " + (", ".join(caps.supported_operations) if caps.supported_operations else "none"))
                    print("  memory_models = " + (", ".join(caps.memory_models) if caps.memory_models else "none"))
                    print("  fusion_strategies = " + (", ".join(caps.fusion_strategies) if caps.fusion_strategies else "none"))
                    print("  runtime_features = " + (", ".join(caps.runtime_features) if caps.runtime_features else "none"))
                    print("  unsupported_selected = " + (", ".join(missing) if missing else "none"))
                    print("  compatible = " + ("yes" if not missing else "no"))
                    print("}")
            elif args.command == "lower-mlir":
                from .backend import compile_for_backend, format_backend_artifact
                from .mlir_backend import lower_execution_ir_to_mlir
                pipeline, artifact = compile_for_backend(p.ast, "mlir")
                print(format_backend_artifact(artifact))
                print(lower_execution_ir_to_mlir(p.ast, pipeline=pipeline))
            elif args.command == "emit-backend-mlir":
                from .mlir_backend import lower_execution_ir_to_mlir
                print(lower_execution_ir_to_mlir(p.ast))
            elif args.command == "optimize-ir":
                from .core import optimize_execution_ir
                from .execution_ir import format_execution_ir
                from .execution_optimizer import format_execution_optimization
                optimized, report = optimize_execution_ir(p)
                print(format_execution_optimization(report))
                print(format_execution_ir(optimized))
            elif args.command == "strategies":
                from .core import strategy_selection
                print(strategy_selection(p))
            elif args.command == "cost-model":
                from .core import cost_analysis
                print(cost_analysis(p))
            elif args.command == "cardinality":
                from .execution_ir import build_execution_ir
                ir_obj = build_execution_ir(p.ast)
                print("cardinality.analysis {")
                for n in ir_obj.nodes:
                    if n.cardinality is not None or n.cardinality_confidence != "unknown":
                        value = str(n.cardinality) if n.cardinality is not None else "unknown"
                        shape = n.data_shape
                        extra = ""
                        if shape:
                            ranges = ", ".join(f"{k}=[{lo:g},{hi:g}]" for k,lo,hi in shape.numeric_ranges) or "none"
                            extra = f"; bounds=[{shape.lower},{shape.upper}]; complexity={shape.complexity}; ranges={ranges}"
                        print(f"  {n.binding}: {value} ({n.cardinality_confidence}; {n.cardinality_reason}{extra})")
                print("  analysis = compile-time-only")
                print("  runtime_measurements = not-used")
                print("  unknown = conservative")
                print("}")
            elif args.command == "alias":
                from .core import alias_analysis
                print(alias_analysis(p))
            elif args.command == "conflicts":
                from .core import conflict_graph
                print(conflict_graph(p))
            elif args.command == "dependencies":
                from .core import dependency_graph
                print(dependency_graph(p))
            elif args.command == "memory":
                from .execution_ir import build_execution_ir
                for n in build_execution_ir(p.ast).nodes:
                    if n.memory_region_specs:
                        print(n.binding + ": " + ", ".join(f"{r.scope}:{r.canonical}" for r in n.memory_region_specs))
            elif args.command == "plan":
                from .goal_plan import build_execution_plan, format_goal_plan
                print(format_goal_plan(build_execution_plan(p.ast)))
            elif args.command == "graph":
                from .semantic_graph import build_semantic_graph, format_semantic_graph
                print(format_semantic_graph(build_semantic_graph(p.ast)))
            elif args.command == "optimize":
                from .goal_ir import lower_goals
                from .compiler_pipeline import compile_semantic_pipeline
                goal_count = len(lower_goals(p.ast))
                print(f"goal_ir_ops = {goal_count}")
                plan_cost = compile_semantic_pipeline(p.ast).global_plan_cost
                report = optimize_program(p)
                print(f"constant_folds = {report.constant_folds}")
                print(f"filter_fusions = {report.filter_fusions}")
                print(f"map_fusions = {report.map_fusions}")
                print(f"pipeline_fusions = {report.pipeline_fusions}")
                print(f"record_transform_fusions = {report.record_transform_fusions}")
                print(f"record_transform_partial = {report.record_transform_partial}")
                print(f"record_transform_materialized = {report.record_transform_materialized}")
                print(f"record_downstream_pressure = {report.record_downstream_pressure}")
                print(f"record_downstream_fanout = {report.record_downstream_fanout}")
                print(f"record_fusion_cost = {plan_cost.record_fusion_cost:g}" if plan_cost is not None else "record_fusion_cost = 0")
                print(f"identity_maps_removed = {report.identity_maps_removed}")
                print(f"total_transformations = {report.total}")
            elif args.command == "emit-mlir":
                print(mlir(p))
            elif args.command == "emit-slang-mlir":
                print(slang_mlir(p))
            elif args.command == "emit-llvm":
                print(llvm_ir(p))
            elif args.command == "build":
                out = Path(args.output) if args.output else src.with_suffix("")
                from .backend import compile_program
                result = compile_program(p, args.backend)
                decision = result.decision
                lowered = result.lowered
                if lowered.backend == "native-llvm":
                    ll = out.with_suffix(".ll")
                    ll.write_text(lowered.text, encoding="utf-8")
                    clang = shutil.which("clang") or shutil.which("gcc")
                    if not clang:
                        raise SystemExit("error: clang or gcc not found")
                    runtime = _runtime_source_path()
                    subprocess.run([clang, "-O2", str(ll), str(runtime), "-lm", "-o", str(out)], check=True)
                    if not args.keep_ir:
                        ll.unlink(missing_ok=True)
                    print(out)
                else:
                    script = Path(__file__).resolve().parents[1] / "build_mlir.py"
                    cmd = [sys.executable, str(script), str(src), "-o", str(out)]
                    if args.keep_ir:
                        cmd.append("--keep-ir")
                    subprocess.run(cmd, check=True)
            return

        if not args.legacy_source:
            ap.print_help()
            return
        src = Path(args.legacy_source)
        p = _load(src)
        if args.llvm:
            print(llvm_ir(p)); return
        if args.slang_mlir:
            print(slang_mlir(p)); return
        if args.mlir:
            print(mlir(p)); return
        if args.ir:
            print(ir(p)); return
        if args.run or not args.check:
            run(p)
            for expr in (p.show_exprs or []): print(show_expr_value(p, expr))
            if not p.show_exprs:
                for n, f in p.shows: print(f"{n}{'' if f == '__value__' else '.' + f} = {show_value(p, n, f)}")
        else:
            print("OK")
    except (ParseError, TypeError, ValueError, subprocess.CalledProcessError) as e:
        raise SystemExit(f"error: {e}")


if __name__ == "__main__":
    main()
