from slang.core import parse, validate, run
from slang.stdlib_runtime import RuntimeCapabilityError, capture_runtime_trace, runtime_effect_policy


def test_legacy_file_names_use_catalog_boundary(tmp_path):
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
    assert names == ['write', 'exists', 'read']
    assert all(event.effect == 'IO' and event.success for event in events)
    assert target.read_text(encoding='utf-8') == 'hello'


def test_legacy_file_names_are_denied_before_side_effect(tmp_path):
    target = tmp_path / 'blocked.txt'
    program = parse(f'let ok = write("{target.as_posix()}", "blocked")\n')
    validate(program)
    try:
        with runtime_effect_policy(allowed_effects={'pure'}, allowed_capabilities={'pure'}):
            run(program)
    except RuntimeCapabilityError:
        pass
    else:
        raise AssertionError('expected filesystem capability denial')
    assert not target.exists()
