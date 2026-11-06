import pytest
from slang import LSPServer


def test_incremental_change_and_save_are_advertised():
    server = LSPServer()
    result = server.initialize()
    assert result["capabilities"]["textDocumentSync"]["change"] == 2
    assert result["capabilities"]["textDocumentSync"]["save"]["includeText"] is True


def test_incremental_change_applies_multiple_ranges():
    server = LSPServer()
    uri = "file:///tmp/example.sl"
    server.did_open(uri, "let a = 1\nlet b = 2\n", version=1)
    payload = server.did_change(uri, [{"range": {"start": {"line": 0, "character": 8}, "end": {"line": 0, "character": 9}}, "text": "3"}], version=2)
    assert server.documents[0].text == "let a = 3\nlet b = 2\n"
    assert payload["version"] == 2


def test_incremental_change_rejects_reversed_range():
    server = LSPServer()
    uri = "file:///tmp/example.sl"
    server.did_open(uri, "let a = 1\n")
    with pytest.raises(ValueError):
        server.did_change(uri, [{"range": {"start": {"line": 0, "character": 9}, "end": {"line": 0, "character": 8}}, "text": "x"}])


def test_did_save_can_refresh_text_and_version():
    server = LSPServer()
    uri = "file:///tmp/example.sl"
    server.did_open(uri, "let a = 1\n", version=1)
    payload = server.did_save(uri, text="let a = 2\n", version=2)
    assert payload["version"] == 2
    assert server.documents[0].text == "let a = 2\n"
