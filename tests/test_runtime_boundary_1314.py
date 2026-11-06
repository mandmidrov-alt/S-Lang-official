from slang.core import parse, validate, run
from slang.stdlib_runtime import RuntimeCapabilityError, capture_runtime_trace, runtime_effect_policy


def test_legacy_filesystem_primitives_use_capability_boundary(tmp_path):
    target = tmp_path / 'legacy.txt'
    program = parse(
        f'let written = write("{target.as_posix()}", "hello")\n'
        f'let present = exists("{target.as_posix()}")\n'
        f'let content = read("{target.as_posix()}")\n'
    )
    validate(program)
    with capture_runtime_trace() as events:
        run(program)
    names = [event.name for event in events]
    assert names.count('write') == 1
    assert names.count('exists') == 1
    assert names.count('read') == 1
    assert all(event.effect == 'IO' for event in events)
    assert all(event.success for event in events)
    assert target.read_text(encoding='utf-8') == 'hello'


def test_legacy_write_is_denied_before_side_effect(tmp_path):
    target = tmp_path / 'blocked.txt'
    program = parse(f'let ok = write("{target.as_posix()}", "blocked")')
    validate(program)
    try:
        with runtime_effect_policy(allowed_effects={'pure'}, allowed_capabilities={'pure'}):
            run(program)
    except RuntimeCapabilityError:
        pass
    else:
        raise AssertionError('expected filesystem capability denial')
    assert not target.exists()


def test_run_program_timeout_uses_registered_runtime_boundary():
    import sys
    program = parse(
        f'let result = run_program_timeout("{sys.executable}", ["-c", "print(\'ok\')"], 2, "")'
    )
    validate(program)
    with capture_runtime_trace() as events:
        run(program)
    matching = [event for event in events if event.name == 'run_program_timeout']
    assert len(matching) == 1
    assert matching[0].effect == 'IO'
    assert matching[0].success
