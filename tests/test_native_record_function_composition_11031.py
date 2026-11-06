import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_TIMEOUT_SECONDS = 45
RUN_TIMEOUT_SECONDS = 10


def _run_bounded(command, *, cwd, timeout, stage):
    """Run a native-build step with a hard timeout and useful failure output."""
    kwargs = {"cwd": cwd, "text": True, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    process = subprocess.Popen(command, **kwargs)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        if os.name == "nt":
            process.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        stdout, stderr = process.communicate()
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        raise AssertionError(
            f"{stage} timed out after {timeout}s.\n"
            f"stdout:\n{stdout or ''}\nstderr:\n{stderr or ''}"
        ) from exc
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def build_run(tmp_path, source):
    src = tmp_path / 'composition.sl'
    out = tmp_path / 'composition'
    src.write_text(source, encoding='utf-8')
    build = _run_bounded(
        [sys.executable, '-m', 'slang.cli', 'build', str(src), '-o', str(out), '--backend', 'native'],
        cwd=ROOT, timeout=BUILD_TIMEOUT_SECONDS, stage='slang.cli build --backend native',
    )
    assert build.returncode == 0, f"native build failed ({build.returncode})\nstdout:\n{build.stdout}\nstderr:\n{build.stderr}"
    result = _run_bounded([str(out)], cwd=ROOT, timeout=RUN_TIMEOUT_SECONDS, stage='compiled native program')
    assert result.returncode == 0, f"native program failed ({result.returncode})\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    return result.stdout.splitlines()

def test_record_returning_function_can_be_passed_to_another_record_function(tmp_path):
    out=build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    score: Number

record Normalized:
    name: Text
    value: Number

record Summary:
    label: Text
    value: Number

function normalize(person: Person) -> Normalized:
    return Normalized(person.name, person.score - person.age)

function summarize(item: Normalized) -> Summary:
    return Summary(item.name, item.value * 2)

function final(person: Person) -> Summary:
    return summarize(normalize(person))

let people = [Person("Ada", 36, 90), Person("Bob", 15, 70)]
result = people map final(row)
values = result map row.value
show values
''')
    assert out == ['108','110']

def test_record_returning_call_field_can_feed_scalar_helper(tmp_path):
    out=build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    score: Number

record Normalized:
    name: Text
    value: Number

function normalize(person: Person) -> Normalized:
    return Normalized(person.name, person.score - person.age)

function double(x: Number) -> Number:
    return x * 2

function summarize(person: Person) -> Number:
    return double(normalize(person).value)

let people = [Person("Ada", 36, 90), Person("Bob", 15, 70)]
result = people map summarize(row)
show result
''')
    assert out == ['108','110']
