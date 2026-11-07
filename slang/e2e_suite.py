"""End-to-end acceptance scenarios spanning source, runtime, packages, and native lowering."""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from .compiler_artifact import CompilerArtifact
from .compiler_pipeline import compile_semantic_pipeline, compiler_artifact
from .core import parse_file
from .backend import lower_compiler_artifact

ROOT = Path(__file__).resolve().parents[1]


def _cli(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    timeout_seconds = float(env.get("SLANG_E2E_CLI_TIMEOUT", "30"))
    env["PYTHONPATH"] = str(ROOT)
    env.setdefault("TERM", "xterm")
    command = [sys.executable, "-c", "import sys; from slang.cli import main; main()", *args]
    # Isolate the CLI in its own process group on POSIX. Native compilation can
    # create grandchildren; killing only the Python parent may leave a compiler
    # or generated executable holding captured stdout/stderr pipes open.
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=(os.name != "nt"),
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        stdout, stderr = process.communicate()
        detail = f"S-Lang CLI timed out after {timeout_seconds:g} seconds: {' '.join(args)}"
        return subprocess.CompletedProcess(
            args=command,
            returncode=124,
            stdout=stdout or "",
            stderr=((stderr or "") + "\n" + detail).strip(),
        )


def _native_artifact_run() -> dict[str, object]:
    _trace("persisted-artifact:parse-start")
    source = ROOT / "examples" / "fused_reduce.sl"
    program = parse_file(source)
    _trace("persisted-artifact:parse-end")
    artifact = compiler_artifact(compile_semantic_pipeline(program.ast), module=program.ast)
    _trace("persisted-artifact:compile-end")
    encoded = artifact.to_json()
    restored = CompilerArtifact.from_json(encoded)
    _trace("persisted-artifact:restore-end")
    lowered = lower_compiler_artifact(restored, "native")
    _trace("persisted-artifact:lower-end")
    compiler = shutil.which("clang") or shutil.which("gcc")
    if not compiler:
        return {
            "name": "persisted-native-artifact",
            "status": "skipped",
            "reason": "clang/gcc unavailable",
            "artifact_round_trip": restored.fingerprint == artifact.fingerprint,
        }
    with tempfile.TemporaryDirectory(prefix="slang-e2e-artifact-") as td:
        root = Path(td)
        ll = root / "program.ll"
        exe = root / ("program.exe" if os.name == "nt" else "program")
        ll.write_text(lowered.text, encoding="utf-8")
        _trace("persisted-artifact:write-ir-end")
        runtime = ROOT / "slang" / "slang_runtime.c"
        timeout_seconds = float(os.environ.get("SLANG_E2E_NATIVE_TIMEOUT", "30"))
        build_command = [compiler, "-O2", str(ll), str(runtime), *( ["-lm"] if os.name != "nt" else [] ), "-o", str(exe)]
        build_process = subprocess.Popen(
            build_command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=(os.name != "nt"),
        )
        try:
            _trace("persisted-artifact:build-start")
            build_stdout, build_stderr = build_process.communicate(timeout=timeout_seconds)
            _trace(f"persisted-artifact:build-end rc={build_process.returncode}")
            build = subprocess.CompletedProcess(build_command, build_process.returncode, build_stdout, build_stderr)
        except subprocess.TimeoutExpired:
            if os.name != "nt":
                try:
                    os.killpg(build_process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                build_process.kill()
            build_stdout, build_stderr = build_process.communicate()
            build = subprocess.CompletedProcess(
                build_command, 124, build_stdout,
                (build_stderr + f"\nNative E2E build timed out after {timeout_seconds:g}s").strip(),
            )
        if build.returncode:
            return {"name": "persisted-native-artifact", "status": "failed", "stage": "build", "stderr": build.stderr[-1000:]}
        run_command = [str(exe)]
        run_process = subprocess.Popen(
            run_command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=(os.name != "nt"),
        )
        try:
            _trace("persisted-artifact:run-start")
            run_stdout, run_stderr = run_process.communicate(timeout=timeout_seconds)
            _trace(f"persisted-artifact:run-end rc={run_process.returncode}")
            run = subprocess.CompletedProcess(run_command, run_process.returncode, run_stdout, run_stderr)
        except subprocess.TimeoutExpired:
            if os.name != "nt":
                try:
                    os.killpg(run_process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                run_process.kill()
            run_stdout, run_stderr = run_process.communicate()
            run = subprocess.CompletedProcess(
                run_command, 124, run_stdout,
                (run_stderr + f"\nNative E2E execution timed out after {timeout_seconds:g}s").strip(),
            )
    return {
        "name": "persisted-native-artifact",
        "status": "passed" if run.returncode == 0 and run.stdout.strip() == "18" else "failed",
        "artifact_round_trip": restored.fingerprint == artifact.fingerprint,
        "backend": lowered.backend,
        "output": run.stdout.strip(),
    }


def _trace(stage: str) -> None:
    if os.environ.get("SLANG_E2E_DIAGNOSTICS") == "1":
        print(f"[e2e] {stage}", file=sys.stderr, flush=True)


def run_suite() -> dict[str, object]:
    cases: list[dict[str, object]] = []

    _trace("case:reference-data-pipeline:start")
    r = _cli("run", "examples/practical_data_pipeline.sl")
    _trace(f"case:reference-data-pipeline:end rc={r.returncode}")
    expected = [
        "[Clara(age=34, score=96), Gina(age=37, score=94), Elena(age=23, score=91), Denis(age=41, score=88), Hugo(age=29, score=86)]",
        "[192, 176, 182, 188, 172]",
        "455",
        "91",
    ]
    cases.append({
        "name": "reference-data-pipeline",
        "status": "passed" if r.returncode == 0 and all(x in r.stdout for x in expected) else "failed",
        "stage": "source->semantic->runtime",
        "source": "examples/practical_data_pipeline.sl",
    })

    _trace("case:stdlib-text-workflow:start")
    r = _cli("run", "examples/practical_text.sl")
    _trace(f"case:stdlib-text-workflow:end rc={r.returncode}")
    cases.append({
        "name": "stdlib-text-workflow",
        "status": "passed" if r.returncode == 0 and "5" in r.stdout and "alpha, beta, gamma, delta, omega" in r.stdout else "failed",
        "stage": "source->stdlib->runtime",
        "source": "examples/practical_text.sl",
    })

    project = ROOT / "examples" / "package_graph" / "src" / "main.sl"
    _trace("case:transitive-package-project:resolve-start")
    resolved = _cli("resolve-packages", str(project))
    _trace(f"case:transitive-package-project:resolve-end rc={resolved.returncode}")

    if resolved.returncode != 0:
        _trace(f"resolve stdout: {resolved.stdout}")
        _trace(f"resolve stderr: {resolved.stderr}")

    locked = _cli("lock", str(project), "--check")
    _trace(f"case:transitive-package-project:lock-end rc={locked.returncode}")

    if locked.returncode != 0:
        _trace(f"lock stdout: {locked.stdout}")
        _trace(f"lock stderr: {locked.stderr}")

    executed = _cli("run", str(project))
    _trace(f"case:transitive-package-project:run-end rc={executed.returncode}")

    if executed.returncode != 0:
        _trace(f"run stdout: {executed.stdout}")
        _trace(f"run stderr: {executed.stderr}")
    cases.append({
        "name": "transitive-package-project",
        "status": "passed" if resolved.returncode == 0 and locked.returncode == 0 and executed.returncode == 0 and "42" in executed.stdout else "failed",
        "stage": "resolve->lock->transitive-import->runtime",
        "source": "examples/package_graph/src/main.sl",
        "packages": 3,
    })

    _trace("case:native-fused-reduction:start")
    native = _cli("run", "examples/fused_reduce.sl", "--native")
    _trace(f"case:native-fused-reduction:end rc={native.returncode}")
    cases.append({
        "name": "native-fused-reduction",
        "status": "passed" if native.returncode == 0 and "18" in native.stdout else "failed",
        "stage": "source->compiler->LLVM->native-runtime",
        "source": "examples/fused_reduce.sl",
    })

    _trace("case:persisted-native-artifact:start")
    cases.append(_native_artifact_run())
    _trace("case:persisted-native-artifact:end")
    passed = sum(1 for c in cases if c["status"] == "passed")
    skipped = sum(1 for c in cases if c["status"] == "skipped")
    return {
        "cases": cases,
        "summary": {
            "cases": len(cases),
            "passed": passed,
            "skipped": skipped,
            "failed": len(cases) - passed - skipped,
            "release_blocking": len(cases) - passed - skipped == 0,
            "scope": "end-to-end source/runtime/stdlib/packages/native/persisted-artifact",
        },
    }
