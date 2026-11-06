from pathlib import Path

from slang.lsp_server import LSPServer


def uri(path: Path) -> str:
    return path.resolve().as_uri()


def labels(items):
    return {item["label"] for item in items}


def test_completion_includes_direct_imported_function(tmp_path):
    provider = tmp_path / "provider.sl"
    consumer = tmp_path / "consumer.sl"
    provider.write_text("function helper(value: Number) -> Number:\n    return value\n", encoding="utf-8")
    consumer.write_text('import "provider.sl"\nlet value = helper(1)\n', encoding="utf-8")

    server = LSPServer(root_uri=uri(tmp_path))
    server.initialize()
    server.did_open(uri(consumer), consumer.read_text(encoding="utf-8"))

    items = server.completion(uri(consumer), 2, 6)
    assert "helper" in labels(items)


def test_signature_help_includes_direct_imported_function(tmp_path):
    provider = tmp_path / "provider.sl"
    consumer = tmp_path / "consumer.sl"
    provider.write_text("function helper(value: Number, text: Text) -> Number:\n    return value\n", encoding="utf-8")
    consumer.write_text('import "provider.sl"\nlet value = helper(1, )\n', encoding="utf-8")

    server = LSPServer(root_uri=uri(tmp_path))
    server.initialize()
    server.did_open(uri(consumer), consumer.read_text(encoding="utf-8"))

    result = server.signature_help(uri(consumer), 1, 22)
    assert result is not None
    assert "helper(value: Number, text: Text) -> Number" in result["signatures"][0]["label"]
    assert result["signatures"][0]["activeParameter"] == 1


def test_closed_dependency_change_updates_completion_and_signature(tmp_path):
    provider = tmp_path / "provider.sl"
    consumer = tmp_path / "consumer.sl"
    provider.write_text("function old_name(value: Number) -> Number:\n    return value\n", encoding="utf-8")
    consumer.write_text('import "provider.sl"\nlet value = old_name(1)\n', encoding="utf-8")

    server = LSPServer(root_uri=uri(tmp_path))
    server.initialize()
    server.did_open(uri(consumer), consumer.read_text(encoding="utf-8"))

    assert "old_name" in labels(server.completion(uri(consumer), 2, 6))

    provider.write_text("function new_name(value: Text) -> Text:\n    return value\n", encoding="utf-8")
    server.did_change_watched_files([{"uri": uri(provider), "type": 2}])

    current = labels(server.completion(uri(consumer), 1, 11))
    assert "new_name" in current
    assert "old_name" not in current

    consumer_text = consumer.read_text(encoding="utf-8").replace("old_name", "new_name")
    server.did_change(uri(consumer), consumer_text, version=2)
    result = server.signature_help(uri(consumer), 1, 22)
    assert result is not None
    assert "new_name(value: Text) -> Text" in result["signatures"][0]["label"]
