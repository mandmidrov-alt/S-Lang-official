"""Clean-environment installation and user-workflow acceptance suite."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import shutil
import tempfile
import venv
from pathlib import Path
from typing import Any


def _run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    timeout = float(os.environ.get("SLANG_INSTALL_STEP_TIMEOUT", "30"))
    process = subprocess.Popen(
        cmd, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, start_new_session=(os.name != "nt"),
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            import signal
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        stdout, stderr = process.communicate()
        detail = f"installation step timed out after {timeout:g}s: {' '.join(cmd)}"
        return subprocess.CompletedProcess(cmd, 124, stdout, (stderr + "\n" + detail).strip())


def run_suite(source_root: str | Path = ".") -> dict[str, Any]:
    root = Path(source_root).resolve()
    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="slang-install-suite-") as td:
        work = Path(td)
        wheelhouse = work / "wheelhouse"
        wheelhouse.mkdir()
        wheel = _run([sys.executable, "-m", "pip", "wheel", str(root), "--no-deps", "--no-build-isolation", "-w", str(wheelhouse)])
        results.append({"step": "build-wheel", "passed": wheel.returncode == 0, "stdout": wheel.stdout[-2000:], "stderr": wheel.stderr[-2000:]})
        if wheel.returncode:
            return {"suite": "installation", "passed": False, "steps": results, "deterministic": True}

        wheels = sorted(wheelhouse.glob("*.whl"))
        if len(wheels) != 1:
            results.append({"step": "wheel-discovery", "passed": False, "count": len(wheels)})
            return {"suite": "installation", "passed": False, "steps": results, "deterministic": True}

        venv_dir = work / "venv"
        venv.EnvBuilder(with_pip=False, clear=True).create(venv_dir)
        python = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        slang = venv_dir / ("Scripts/slang.exe" if os.name == "nt" else "bin/slang")
        clean_env = dict(os.environ)
        clean_env.pop("PYTHONPATH", None)
        install = _run([sys.executable, "-m", "pip", "--python", str(python), "install", "--force-reinstall", "--no-index", "--no-deps", str(wheels[0])], env=clean_env)
        results.append({"step": "install-wheel", "passed": install.returncode == 0, "stdout": install.stdout[-2000:], "stderr": install.stderr[-2000:]})
        if install.returncode:
            return {"suite": "installation", "passed": False, "steps": results, "deterministic": True}

        # Prefer the installed console script. If a platform's pip layout does not
        # expose it at the canonical venv path, use the installed package entry
        # point through Python so the remainder of the workflow still verifies the
        # actual wheel; report the console-script state explicitly.
        script_present = slang.is_file()
        entrypoint_check = _run([str(python), "-c",
            "import importlib.metadata as m; eps=[e for e in m.entry_points(group='console_scripts') if e.name == 'slang']; print(len(eps) and eps[0].value or '')"])
        entrypoint_ok = entrypoint_check.returncode == 0 and entrypoint_check.stdout.strip() == "slang.cli:main"
        results.append({"step": "console-script", "passed": script_present and entrypoint_ok, "script_present": script_present, "entrypoint": entrypoint_check.stdout.strip(), "stderr": entrypoint_check.stderr[-1000:]})
        if script_present:
            slang_cmd = [str(slang)]
        else:
            slang_cmd = [str(python), "-c", "import sys; from slang.cli import main; main()"]

        doctor = _run([*slang_cmd, "doctor"], env=clean_env)
        results.append({"step": "installed-doctor", "passed": doctor.returncode == 0, "stdout": doctor.stdout[-2000:], "stderr": doctor.stderr[-2000:]})

        project = work / "sample-project"
        init = _run([*slang_cmd, "init", str(project), "--name", "sample-app", "--version", "0.1.0"], env=clean_env)
        results.append({"step": "init-project", "passed": init.returncode == 0, "stdout": init.stdout[-2000:], "stderr": init.stderr[-2000:]})
        if init.returncode:
            return {"suite": "installation", "passed": False, "steps": results, "deterministic": True}

        resolve = _run([*slang_cmd, "resolve-packages", str(project)], env=clean_env)
        results.append({"step": "resolve-packages", "passed": resolve.returncode == 0, "stdout": resolve.stdout[-2000:], "stderr": resolve.stderr[-2000:]})
        lock = _run([*slang_cmd, "lock", str(project)], env=clean_env)
        results.append({"step": "write-lock", "passed": lock.returncode == 0, "stdout": lock.stdout[-2000:], "stderr": lock.stderr[-2000:]})
        lock_check = _run([*slang_cmd, "lock", str(project), "--check"], env=clean_env)
        results.append({"step": "check-lock", "passed": lock_check.returncode == 0, "stdout": lock_check.stdout[-2000:], "stderr": lock_check.stderr[-2000:]})

        source = project / "src" / "main.sl"
        check = _run([*slang_cmd, "check", str(source)], env=clean_env)
        results.append({"step": "check-project", "passed": check.returncode == 0, "stdout": check.stdout[-2000:], "stderr": check.stderr[-2000:]})
        run = _run([*slang_cmd, "run", str(source)], env=clean_env)
        results.append({"step": "run-project", "passed": run.returncode == 0 and run.stdout.strip() == "0", "stdout": run.stdout[-2000:], "stderr": run.stderr[-2000:]})

        build_out = work / ("sample-native.exe" if os.name == "nt" else "sample-native")
        build = _run([*slang_cmd, "build", str(source), "-o", str(build_out), "--backend", "native"], env=clean_env)
        native_ok = build.returncode == 0 and build_out.is_file()
        results.append({"step": "native-build", "passed": native_ok, "stdout": build.stdout[-2000:], "stderr": build.stderr[-2000:]})
        if native_ok:
            native_run = _run([str(build_out)], env=clean_env)
            results.append({"step": "native-run", "passed": native_run.returncode == 0, "stdout": native_run.stdout[-2000:], "stderr": native_run.stderr[-2000:]})
        else:
            compiler_available = shutil.which("clang") or shutil.which("gcc")
            if compiler_available:
                results.append({"step": "native-run", "passed": False, "skipped": False, "reason": "native build failed despite compiler availability"})
            else:
                results.append({"step": "native-run", "passed": True, "skipped": True, "reason": "native compiler unavailable"})

    return {
        "suite": "installation",
        "passed": all(step["passed"] for step in results),
        "steps": results,
        "workflow": ["install", "init", "resolve", "lock", "check", "run", "native-build", "native-run"],
        "deterministic": True,
    }
