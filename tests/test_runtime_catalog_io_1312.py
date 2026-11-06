from slang.core import parse, validate, run
from slang.stdlib_runtime import RuntimeCapabilityError, capture_runtime_trace, runtime_effect_policy


def test_catalog_filesystem_call_is_denied_before_side_effect(tmp_path):
    target = tmp_path / 'blocked.txt'
    source = f'let ok = write_json("{target.as_posix()}", "blocked")'
    p = parse(source)
    validate(p)
    try:
        with runtime_effect_policy(allowed_effects={'pure'}, allowed_capabilities={'pure'}):
            run(p)
    except RuntimeCapabilityError:
        pass
    else:
        raise AssertionError('expected filesystem capability denial')
    assert not target.exists()


def test_catalog_csv_calls_share_runtime_boundary(tmp_path):
    source_file = tmp_path / 'input.csv'
    output_file = tmp_path / 'output.csv'
    source_file.write_text('name,age\nAda,36\n', encoding='utf-8')
    program = parse(
        f'let rows = read_csv("{source_file.as_posix()}")\n'
        f'let written = write_csv("{output_file.as_posix()}", rows)\n'
    )
    validate(program)
    with capture_runtime_trace() as events:
        run(program)
    names = [event.name for event in events]
    assert 'read_csv' in names
    assert 'write_csv' in names
    assert all(event.effect == 'IO' for event in events if event.name in {'read_csv', 'write_csv'})
    assert all(event.success for event in events if event.name in {'read_csv', 'write_csv'})
    assert output_file.read_text(encoding='utf-8') == 'name,age\nAda,36\n'
