from slang import LSPJsonRpcServer


def initialize(rpc):
    return rpc.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})


def test_session_lifecycle_states():
    rpc = LSPJsonRpcServer()
    assert rpc.session_state == "created"
    initialize(rpc)
    assert rpc.session_state == "initialized"
    assert rpc.handle_message({"jsonrpc": "2.0", "method": "initialized"}) == ()
    assert rpc.handle_message({"jsonrpc": "2.0", "id": 2, "method": "shutdown"}) == ({"jsonrpc": "2.0", "id": 2, "result": None},)
    assert rpc.session_state == "shutdown"
    assert rpc.handle_message({"jsonrpc": "2.0", "method": "exit"}) == ()
    assert rpc.exit_requested is True


def test_initialize_twice_is_invalid_request():
    rpc = LSPJsonRpcServer()
    initialize(rpc)
    response = rpc.handle_message({"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {}})[0]
    assert response["error"]["code"] == -32600


def test_messages_after_shutdown_are_rejected():
    rpc = LSPJsonRpcServer()
    initialize(rpc)
    rpc.handle_message({"jsonrpc": "2.0", "id": 2, "method": "shutdown"})
    response = rpc.handle_message({"jsonrpc": "2.0", "id": 3, "method": "textDocument/didOpen", "params": {}})[0]
    assert response["error"]["code"] == -32600
    assert response["error"]["message"] == "Server is shutting down"


def test_initialized_before_initialize_is_invalid_request():
    rpc = LSPJsonRpcServer()
    assert rpc.handle_message({"jsonrpc": "2.0", "method": "initialized"}) == ()
