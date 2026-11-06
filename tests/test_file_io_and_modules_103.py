from pathlib import Path

from slang.core import parse_file, validate, run, show_value


def test_file_io_builtins(tmp_path):
    source = tmp_path / "io.sl"
    target = tmp_path / "data.txt"
    lines_target = tmp_path / "lines.txt"
    source.write_text(
        f'''let path = "{target.as_posix()}"\n'''
        f'''let lines_path = "{lines_target.as_posix()}"\n'''
        '''let wrote = write(path, "alpha\\nbeta")\n'''
        '''let text = read(path)\n'''
        '''let lines = read_lines(path)\n'''
        '''let wrote_lines = write_lines(lines_path, lines)\n'''
        '''let exists_now = exists(lines_path)\n'''
        '''show text\n'''
        '''show lines\n''',
        encoding="utf-8",
    )
    p = parse_file(source)
    validate(p)
    run(p)
    assert show_value(p, "text", "__value__") == "alpha\nbeta"
    assert show_value(p, "exists_now", "__value__") == "True"
    assert lines_target.read_text(encoding="utf-8") == "alpha\nbeta\n"


def test_source_module_imports(tmp_path):
    lib = tmp_path / "math.sl"
    main = tmp_path / "main.sl"
    lib.write_text(
        'module mathlib\n'
        'function triple(value: Number) -> Number:\n'
        '    return value * 3\n',
        encoding="utf-8",
    )
    main.write_text(
        'import "math.sl"\n'
        'let answer = triple(7)\n'
        'show answer\n',
        encoding="utf-8",
    )
    p = parse_file(main)
    validate(p)
    run(p)
    assert show_value(p, "answer", "__value__") == "21"
