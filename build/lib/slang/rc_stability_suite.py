"""Final stability and recovery acceptance suite for S-Lang release candidates."""
from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .compiler_artifact import CompilerArtifact
from .e2e_suite import run_suite as run_e2e_suite
from .installation_suite import run_suite as run_installation_suite

ROOT = Path(__file__).resolve().parents[1]


def _cli(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    command = [sys.executable, "-c", "import sys; from slang.cli import main; raise SystemExit(main())", *args]
    timeout_seconds = float(env.get("SLANG_RC_CLI_TIMEOUT", "15"))
    process = subprocess.Popen(
        command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, start_new_session=(os.name != "nt"),
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
        detail = f"stability CLI timed out after {timeout_seconds:g}s: {' '.join(args)}"
        return subprocess.CompletedProcess(command, 124, stdout or "", ((stderr or "") + "\n" + detail).strip())


def _repeat_e2e() -> dict[str, Any]:
    fingerprints: list[str] = []
    summaries: list[dict[str, Any]] = []
    for index in range(3):
        if os.environ.get("SLANG_RC_DIAGNOSTICS") == "1":
            print(f"[rc-stability] e2e:{index + 1}:start", file=sys.stderr, flush=True)
        result = run_e2e_suite()
        summaries.append(result["summary"])
        fingerprints.append(hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest())
        if os.environ.get("SLANG_RC_DIAGNOSTICS") == "1":
            print(f"[rc-stability] e2e:{index + 1}:end", file=sys.stderr, flush=True)
    return {
        "passed": all(s["release_blocking"] for s in summaries),
        "runs": len(summaries),
        "deterministic_report": len(set(fingerprints)) == 1,
        "fingerprints": fingerprints,
    }


def _error_recovery() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="slang-stability-recovery-") as td:
        root = Path(td)
        invalid = root / "invalid.sl"
        invalid.write_text("this is not valid S-Lang !!!\n", encoding="utf-8")
        bad = _cli("check", str(invalid), cwd=root)
        valid = root / "valid.sl"
        valid.write_text("let answer = 42\nshow answer\n", encoding="utf-8")
        good = _cli("run", str(valid), cwd=root)
        missing = root / "missing_package.sl"
        missing.write_text("import definitely_missing_package\nshow answer\n", encoding="utf-8")
        missing_result = _cli("check", str(missing), cwd=root)
        good_again = _cli("run", str(valid), cwd=root)
    return {
        "passed": bad.returncode != 0 and good.returncode == 0 and good.stdout.strip() == "42"
        and missing_result.returncode != 0 and good_again.returncode == 0,
        "invalid_source_rejected": bad.returncode != 0,
        "valid_source_recovered": good.returncode == 0,
        "missing_dependency_rejected": missing_result.returncode != 0,
        "post_error_recovery": good_again.returncode == 0,
    }


def _artifact_corruption_recovery() -> dict[str, Any]:
    from .compiler_pipeline import compile_semantic_pipeline, compiler_artifact
    from .core import parse_file
    source = ROOT / "examples" / "fused_reduce.sl"
    program = parse_file(source)
    artifact = compiler_artifact(compile_semantic_pipeline(program.ast), module=program.ast)
    payload = json.loads(artifact.to_json())
    payload["fingerprint"] = "0" * 64
    rejected = False
    try:
        CompilerArtifact.from_json(json.dumps(payload))
    except Exception:
        rejected = True
    restored = CompilerArtifact.from_json(artifact.to_json())
    return {
        "passed": rejected and restored.fingerprint == artifact.fingerprint,
        "corrupt_artifact_rejected": rejected,
        "valid_artifact_recovered": restored.fingerprint == artifact.fingerprint,
    }


def run_suite() -> dict[str, Any]:
    import time
    _started = time.monotonic()
    def _stage(name: str) -> None:
        if os.environ.get("SLANG_RC_DIAGNOSTICS") == "1":
            print(f"[rc-stability] {name} (+{time.monotonic() - _started:.2f}s)", file=sys.stderr, flush=True)
    # Run the clean installation first. On constrained CI/container runners,
    # native compilation performed by the E2E matrix can leave the pip wheel
    # installer unusually slow when it is invoked afterward in the same parent
    # process. Keeping packaging isolated and first avoids that order-dependent
    # interaction while still running every acceptance gate.
    _stage("installation:start")
    installation = run_installation_suite(ROOT)
    _stage(f"installation:end passed={installation.get('passed')}")
    e2e = _repeat_e2e()
    _stage(f"e2e:end runs={e2e.get('runs')} deterministic={e2e.get('deterministic_report')}")
    recovery = _error_recovery()
    _stage(f"recovery:end passed={recovery.get('passed')}")
    artifact = _artifact_corruption_recovery()
    _stage(f"artifact:end passed={artifact.get('passed')}")
    checks = {
        "repeated_e2e": e2e["passed"],
        "e2e_report_determinism": e2e["deterministic_report"],
        "error_recovery": recovery["passed"],
        "artifact_recovery": artifact["passed"],
        "clean_installation": installation["passed"],
    }
    return {
        "suite": "rc-stability",
        "release_candidate": True,
        "passed": all(checks.values()),
        "checks": checks,
        "repeated_e2e": e2e,
        "error_recovery": recovery,
        "artifact_recovery": artifact,
        "installation": {"passed": installation["passed"], "workflow": installation["workflow"]},
    }
