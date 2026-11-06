from slang.stdlib.catalog import entries


def test_stdlib_catalog_contains_pure_and_io_surfaces():
    rows = {row["name"]: row for row in entries()}
    assert rows["sqrt"]["effect"] == "pure"
    assert rows["split"]["module"] == "slang.stdlib.text"
    assert rows["read_csv"]["effect"] == "IO"
    assert rows["run_program"]["module"] == "slang.stdlib.process"


def test_stdlib_catalog_is_deterministically_ordered():
    rows = entries()
    assert [row["name"] for row in rows] == sorted(row["name"] for row in rows)


def test_every_catalog_entry_has_user_readable_metadata():
    rows = entries()
    assert rows
    for row in rows:
        assert row["description"].strip(), row["name"]
        assert row["module"].startswith("slang.stdlib."), row["name"]
        assert row["effect"] in {"pure", "IO"}, row["name"]
        assert row.get("capability"), row["name"]
