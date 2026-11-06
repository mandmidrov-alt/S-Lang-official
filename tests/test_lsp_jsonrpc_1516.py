import json

from slang import (
    CONTENT_TYPE,
    INVALID_PARAMS,
    LSPJsonRpcServer,
    JsonRpcFramer,
    decode_message,
    encode_message,
    serialize_message,
)


def test_initialize_request_returns_jsonrpc_response_and_capabilities():
    rpc = LSPJsonRpcServer()
    messages = rpc.handle_message({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"rootUri": "file:///tmp/project", "workspaceFolders": []},
    })
    assert len(messages) == 1
    assert messages[0]["id"] == 1
    assert messages[0]["result"]["serverInfo"]["version"] == "1.0"
    assert messages[0]["result"]["capabilities"]["textDocumentSync"]["change"] == 2


def test_open_notification_emits_publish_diagnostics_notification():
    rpc = LSPJsonRpcServer()
    rpc.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    messages = rpc.handle_message({
        "jsonrpc": "2.0", "method": "textDocument/didOpen",
        "params": {"textDocument": {"uri": "file:///tmp/example.sl", "languageId": "slang", "version": 1, "text": 'let x = 1 + "text"\n'}},
    })
    assert len(messages) == 1
    assert messages[0]["method"] == "textDocument/publishDiagnostics"
    assert messages[0]["params"]["diagnostics"][0]["code"] == "E2000"


def test_incremental_change_is_forwarded_to_lsp_core():
    rpc = LSPJsonRpcServer()
    rpc.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    uri = "file:///tmp/example.sl"
    rpc.handle_message({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {"textDocument": {"uri": uri, "version": 1, "text": "let x = 1\n"}}})
    messages = rpc.handle_message({
        "jsonrpc": "2.0", "method": "textDocument/didChange",
        "params": {"textDocument": {"uri": uri, "version": 2}, "contentChanges": [{"range": {"start": {"line": 0, "character": 8}, "end": {"line": 0, "character": 9}}, "text": "2"}]},
    })
    assert messages[0]["params"]["version"] == 2
    assert messages[0]["params"]["diagnostics"] == []
    assert rpc.server.documents[0].text == "let x = 2\n"


def test_shutdown_is_request_response_and_exit_is_notification():
    rpc = LSPJsonRpcServer()
    rpc.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert rpc.handle_message({"jsonrpc": "2.0", "id": 2, "method": "shutdown"}) == ({"jsonrpc": "2.0", "id": 2, "result": None},)
    assert rpc.server.shutdown_requested is True
    assert rpc.handle_message({"jsonrpc": "2.0", "method": "exit"}) == ()
    assert rpc.exit_requested is True


def test_unknown_method_returns_standard_error():
    rpc = LSPJsonRpcServer()
    rpc.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    response = rpc.handle_message({"jsonrpc": "2.0", "id": 9, "method": "slang/unknown", "params": {}})[0]
    assert response["error"]["code"] == -32601
    assert response["id"] == 9


def test_invalid_params_returns_standard_error():
    rpc = LSPJsonRpcServer()
    rpc.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    response = rpc.handle_message({"jsonrpc": "2.0", "id": 2, "method": "textDocument/didOpen", "params": {}})[0]
    assert response["error"]["code"] == INVALID_PARAMS


def test_deterministic_json_serialization_and_content_length_framing():
    message = {"jsonrpc": "2.0", "id": 4, "result": {"b": 2, "a": "тест"}}
    body = serialize_message(message)
    framed = encode_message(message)
    assert body == json.dumps(message, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert framed.startswith(f"Content-Length: {len(body)}\r\nContent-Type: {CONTENT_TYPE}\r\n\r\n".encode("ascii"))
    assert decode_message(framed) == message


def test_full_text_change_form_is_supported():
    rpc = LSPJsonRpcServer()
    rpc.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    uri = "file:///tmp/example.sl"
    rpc.handle_message({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {"textDocument": {"uri": uri, "version": 1, "text": "let x = 1\n"}}})
    messages = rpc.handle_message({
        "jsonrpc": "2.0", "method": "textDocument/didChange",
        "params": {"textDocument": {"uri": uri, "version": 2}, "contentChanges": [{"text": "let x = 3\n"}]},
    })
    assert messages[0]["params"]["diagnostics"] == []
    assert rpc.server.documents[0].text == "let x = 3\n"


def test_notification_errors_are_not_returned_as_jsonrpc_responses():
    rpc = LSPJsonRpcServer()
    assert rpc.handle_message({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {}}) == ()


def test_incremental_framer_accepts_partial_and_multiple_messages():
    first = encode_message({"jsonrpc": "2.0", "id": 1, "result": {"ok": True}})
    second = encode_message({"jsonrpc": "2.0", "method": "initialized"})
    framer = JsonRpcFramer()
    assert framer.feed(first[:11]) == ()
    assert framer.feed(first[11:] + second) == (
        {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}},
        {"jsonrpc": "2.0", "method": "initialized"},
    )
