import pytest

from slang.stdlib.csv import CSVDataError, read_csv


def test_csv_rejects_duplicate_headers_with_correction(tmp_path):
    path = tmp_path / "duplicate.csv"
    path.write_text("name,name\nAda,Byron\n", encoding="utf-8")

    with pytest.raises(CSVDataError, match="duplicate column name") as exc:
        read_csv(str(path))

    assert "rename the columns" in str(exc.value)


def test_csv_rejects_blank_header_with_position(tmp_path):
    path = tmp_path / "blank-header.csv"
    path.write_text("name,,age\nAda,unused,36\n", encoding="utf-8")

    with pytest.raises(CSVDataError, match="empty column name at position 2") as exc:
        read_csv(str(path))

    assert "give every column a name" in str(exc.value)


@pytest.mark.parametrize(
    ("contents", "expected"),
    [
        ("name,age\nAda\n", "missing 1 field"),
        ("name,age\nAda,36,extra\n", "extra field"),
    ],
)
def test_csv_rejects_rows_with_wrong_field_count(tmp_path, contents, expected):
    path = tmp_path / "wrong-width.csv"
    path.write_text(contents, encoding="utf-8")

    with pytest.raises(CSVDataError, match=expected) as exc:
        read_csv(str(path))

    assert "line 2" in str(exc.value)
    assert "check separators and quoted values" in str(exc.value)


def test_csv_reports_unclosed_quotes_and_line(tmp_path):
    path = tmp_path / "quotes.csv"
    path.write_text('name,notes\nAda,"missing close\n', encoding="utf-8")

    with pytest.raises(CSVDataError, match="CSV syntax is invalid at line 2") as exc:
        read_csv(str(path))

    assert "quotation marks" in str(exc.value)


def test_csv_keeps_valid_quoted_fields_and_blank_lines(tmp_path):
    path = tmp_path / "valid.csv"
    path.write_text('name,notes\nAda,"likes, commas"\n\nGrace,"said ""hello"""\n', encoding="utf-8")

    assert read_csv(str(path)) == [
        {"name": "Ada", "notes": "likes, commas"},
        {"name": "Grace", "notes": 'said "hello"'},
    ]
