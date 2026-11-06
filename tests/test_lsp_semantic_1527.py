from slang.lsp_server import LSPServer


def uri(name):
    return "file:///tmp/" + name


def test_rename_only_targets_resolved_local_symbol():
    server = LSPServer(); server.initialize()
    u = uri("main.sl")
    server.did_open(u, "let value = 1\nfunction f(value: Number) -> Number:\n    let x = value\n    return x\nlet out = value\n")
    edit = server.rename(u, 2, 14, "amount")
    assert edit is not None
    edits = edit["changes"][u]
    assert len(edits) == 2  # parameter + its local use
    assert all(e["newText"] == "amount" for e in edits)
    starts = {(e["range"]["start"]["line"], e["range"]["start"]["character"]) for e in edits}
    assert (0, 4) not in starts
    assert (3, 11) not in starts


def test_rename_top_level_does_not_rename_shadowing_parameter():
    server = LSPServer(); server.initialize()
    u = uri("main.sl")
    server.did_open(u, "let value = 1\nfunction f(value: Number) -> Number:\n    return value\nlet out = value\n")
    edit = server.rename(u, 0, 6, "total")
    assert edit is not None
    starts = {(e["range"]["start"]["line"], e["range"]["start"]["character"]) for e in edit["changes"][u]}
    assert (0, 4) in starts
    assert (2, 11) not in starts
    assert (3, 10) in starts


def test_prepare_rename_resolves_parameter_declaration():
    server = LSPServer(); server.initialize()
    u = uri("main.sl")
    server.did_open(u, "function f(value: Number) -> Number:\n    return value\n")
    prepared = server.prepare_rename(u, 1, 11)
    assert prepared["placeholder"] == "value"
    assert prepared["range"]["start"]["line"] == 0


def test_same_scope_collision_is_rejected():
    server = LSPServer(); server.initialize()
    u = uri("main.sl")
    server.did_open(u, "let value = 1\nlet total = 2\nlet out = value\n")
    assert server.rename(u, 2, 11, "total") is None
