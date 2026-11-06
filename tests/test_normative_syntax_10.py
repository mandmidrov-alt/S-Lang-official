"""Conformance tests for the S-Lang 1.0 language grammar."""

import pytest

from slang.core import ParseError, parse, validate, run


def test_core_expressions_and_literals_parse():
    parse('''
let whole = 12
let decimal = 2.5
let enabled = true
let title = "S-Lang"
let values = [1, 2, 3]
let person = {name: "Ada", age: 36}
let result = if enabled then person.age + whole else whole
show result
''')


def test_state_and_block_if_parse():
    parse('''
state counter = 0
set counter = counter + 1
if counter >= 1:
    show "ready"
else:
    show "not ready"
''')


def test_function_generic_record_entity_and_property_parse():
    parse('''
record Box<T>:
    value: T
entity Circle:
    radius: m
property Circle.diameter -> m:
    return self.radius * 2
function identity<T>(value: T) -> T:
    return value
let box = Box(7)
let disk = Circle(2 m)
let result = identity(box.value)
show result, disk.diameter
''')


def test_collection_statement_forms_parse():
    parse('''
let values = [1, 2, 3, 4, 5]
let selected = values where item >= 3
let doubled = selected map item * 2
let ordered = doubled sort by item desc
let total = ordered sum item
let count = ordered count
let reduced = ordered reduce 0 with acc + item
show total, count, reduced
''')


def test_pipeline_explicit_item_form_parses_and_executes():
    source = '''
let values = [1, 2, 3, 4, 5]
let result = values |> where item >= 3 |> map item * 2 |> sort by item desc |> sum
show result
'''
    program = parse(source)
    validate(program)
    run(program)
    assert program._collections["result"] == 24


def test_pipeline_compact_shorthand_form_parses_and_executes():
    source = '''
let values = [1, 2, 3, 4, 5]
let result = values |> where >= 3 |> map * 2 |> sum
show result
'''
    program = parse(source)
    validate(program)
    run(program)
    assert program._collections["result"] == 24


def test_pipeline_is_single_physical_line_in_1088():
    source = '''
let values = [1, 2, 3, 4, 5]
let result = values
    |> where item >= 3
    |> map item * 2
    |> sum
'''
    with pytest.raises(ParseError):
        parse(source)


def test_sales_analysis_example_executes_with_expected_results():
    source = '''
let sales = [120, 85, 240, 160, 95, 310, 180, 70]
let eligible_sales = sales |> where item >= 100 |> map item * 0.9 |> sort by item desc
let premium_sales = eligible_sales |> where item >= 150
let total_revenue = eligible_sales sum item
let premium_revenue = premium_sales sum item
let average_sale = eligible_sales average item
show eligible_sales
show premium_sales
show total_revenue
show premium_revenue
show average_sale
'''
    program = parse(source)
    validate(program)
    run(program)
    assert program._collections["eligible_sales"] == [279.0, 216.0, 162.0, 144.0, 108.0]
    assert program._collections["premium_sales"] == [279.0, 216.0, 162.0]
    assert program._collections["total_revenue"] == 909
    assert program._collections["premium_revenue"] == 657
    assert program._collections["average_sale"] == 181.8


def test_module_import_and_reexport_forms_parse(tmp_path):
    (tmp_path / "geometry.sl").write_text('module geometry\nexport Circle\nentity Circle:\n    radius: m\n', encoding="utf-8")
    (tmp_path / "main.sl").write_text('''module sample
import "geometry.sl" as geo
import std.math
export Circle, circumference
export {Circle} from "geometry.sl"
''', encoding="utf-8")
    from slang.core import parse_file
    parse_file(tmp_path / "main.sl")


def test_data_graph_and_satisfy_forms_parse():
    parse('''
data students:
    Alice age 22 score 91
    Bob age 17 score 88
graph routes:
    A -> B cost 2
    B <-> C cost 3
solution = satisfy:
    x in 1..10
    y in 1..10
    x + y == 12
''')


def test_sequence_forms_parse():
    parse('''
sequence doubled from 1 for 5 steps using value * 2
sequence bounded from 1 for up to 10 steps until value >= 100 using value * 2
''')


def test_lambda_syntax_is_not_part_of_expression_grammar():
    with pytest.raises(ParseError):
        parse('let mapped = values map x -> x * 2')


def test_domain_specific_data_graph_satisfy_and_physics_forms_validate():
    source = '''
data students:
    Alice age 22 score 91
    Bob age 17 score 88
let adults = students where age >= 18
let ranked = adults sort by score desc
graph routes:
    A -> B cost 2
    B <-> C cost 3
solution = satisfy:
    x in 1..10
    y in 1..10
    x + y == 12
physics gravity
body sun:
    mass 1 kg
    position 0 m
    velocity 0 mps
body earth:
    mass 1 kg
    position 1 m
    velocity 1 mps
simulate earth around sun for 1 day step 1 minute
'''
    program = parse(source)
    validate(program)
    run(program)
    assert program.data_tables["students"][0]["age"] == 22


def test_circle_declaration_validates():
    program = parse("circle orbit:\n    radius 10 m\n    center 0 m\n")
    validate(program)
    run(program)


def test_all_concrete_slang_examples_in_english_manual_parse():
    """Executable examples in the English S-Lang 1.0 manual stay parser-valid."""
    import re
    from pathlib import Path

    root = Path(__file__).parents[1]
    manual = (root / "docs/latex/S-Lang_1.0_User_Manual_EN.tex").read_text(encoding="utf-8")
    blocks = re.findall(
        r"\\begin\{lstlisting\}(\[[^]]*\])?\s*(.*?)\\end\{lstlisting\}",
        manual,
        re.DOTALL,
    )
    assert len(blocks) >= 30
    checked = 0
    for index, (options, source) in enumerate(blocks, start=1):
        if options and "language={}" in options:
            continue
        source = source.strip("\n")
        if not source.strip():
            continue
        if re.search(r"^(module |import |export )", source, re.MULTILINE):
            continue
        try:
            parse(source)
            checked += 1
        except Exception as exc:
            pytest.fail(f"manual S-Lang example #{index} no longer parses: {exc}\n{source}")
    assert checked >= 30


def test_unsupported_python_style_loop_and_indexing_forms_are_rejected():
    for source in (
        "for item in values:\n    show item\n",
        "while true:\n    show 1\n",
        "let first = values[0]\n",
        "let mapped = values map item -> item * 2\n",
    ):
        with pytest.raises(ParseError):
            parse(source)


def test_compact_field_pipeline_and_conditional_pipeline_execute():
    source = '''
data rows:
    a score 10
    b score 20
    c score 30
let result = rows |> where .score >= 20 |> map .score * 2 |> sum
'''
    program = parse(source)
    validate(program)
    run(program)
    assert program._collections["result"] == 100


def test_expression_precedence_matches_normative_reference():
    source = '''
let power = 2 ^ 3 ^ 2
let negative_power = -2 ^ 2
let logical = not false and true
'''
    program = parse(source)
    validate(program)
    run(program)
    assert program._bindings["power"] == 512
    assert program._bindings["negative_power"] == -4
    assert program._bindings["logical"] is True


def test_comments_are_allowed_after_code_and_preserve_hashes_in_strings():
    source = '''
let label = "S-Lang # language" # trailing comment
let alternate = 'text # kept in string' # another comment
let total = 2 + 3 # arithmetic comment
show label, alternate, total # output comment
'''
    program = parse(source)
    validate(program)
    run(program)
    assert program._bindings["label"] == "S-Lang # language"
    assert program._bindings["alternate"] == "text # kept in string"
    assert program._bindings["total"] == 5


def test_full_line_comments_and_indented_comments_are_ignored():
    source = '''
# module-level comment
if true:
    # indented comment inside a block
    show "ok" # trailing comment inside a block
'''
    program = parse(source)
    validate(program)
    run(program)
