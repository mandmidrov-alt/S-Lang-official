from slang.lsp_jsonrpc import LSPJsonRpcServer


def _initialize(server, capabilities=None):
    init = server.handle_message({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "rootUri": "file:///tmp/project",
            "capabilities": capabilities or {},
            "workspaceFolders": [{"uri": "file:///tmp/project", "name": "project"}],
        },
    })
    assert init and init[0]["id"] == 1
    return server.handle_message({"jsonrpc": "2.0", "method": "initialized", "params": {}})


def test_dynamic_file_watch_registration_is_requested_when_supported():
    server = LSPJsonRpcServer()
    outbound = _initialize(server, {"workspace": {"didChangeWatchedFiles": {"dynamicRegistration": True}}})
    registrations = [m for m in outbound if m.get("method") == "client/registerCapability"]
    assert len(registrations) == 1
    request = registrations[0]
    assert request["id"] == 1
    registration = request["params"]["registrations"][0]
    assert registration["method"] == "workspace/didChangeWatchedFiles"
    assert registration["registerOptions"]["watchers"] == [{"globPattern": "**/*.sl", "kind": 7}]


def test_dynamic_watch_registration_and_configuration_use_distinct_request_ids():
    server = LSPJsonRpcServer()
    outbound = _initialize(server, {
        "workspace": {
            "didChangeWatchedFiles": {"dynamicRegistration": True},
            "configuration": True,
        }
    })
    requests = [m for m in outbound if "method" in m]
    assert [m["id"] for m in requests] == [1, 2]
    assert {m["method"] for m in requests} == {"client/registerCapability", "workspace/configuration"}


def test_registration_response_is_consumed_without_extra_message():
    server = LSPJsonRpcServer()
    outbound = _initialize(server, {"workspace": {"didChangeWatchedFiles": {"dynamicRegistration": True}}})
    request_id = next(m["id"] for m in outbound if m.get("method") == "client/registerCapability")
    assert server.handle_message({"jsonrpc": "2.0", "id": request_id, "result": None}) == ()


def test_registration_is_not_requested_without_dynamic_registration_capability():
    server = LSPJsonRpcServer()
    outbound = _initialize(server, {"workspace": {"didChangeWatchedFiles": {"dynamicRegistration": False}}})
    assert not any(m.get("method") == "client/registerCapability" for m in outbound)


def test_shutdown_unregisters_registered_dynamic_file_watch():
    server = LSPJsonRpcServer()
    outbound = _initialize(server, {"workspace": {"didChangeWatchedFiles": {"dynamicRegistration": True}}})
    register_id = next(m["id"] for m in outbound if m.get("method") == "client/registerCapability")
    assert server.handle_message({"jsonrpc": "2.0", "id": register_id, "result": None}) == ()
    shutdown = server.handle_message({"jsonrpc": "2.0", "id": 9, "method": "shutdown", "params": {}})
    assert shutdown[0] == {"jsonrpc": "2.0", "id": 9, "result": None}
    assert shutdown[1]["method"] == "client/unregisterCapability"
    assert shutdown[1]["params"]["unregistrations"] == [{"id": "slang-workspace-file-watch", "method": "workspace/didChangeWatchedFiles"}]


def test_shutdown_does_not_unregister_when_registration_was_rejected():
    server = LSPJsonRpcServer()
    outbound = _initialize(server, {"workspace": {"didChangeWatchedFiles": {"dynamicRegistration": True}}})
    register_id = next(m["id"] for m in outbound if m.get("method") == "client/registerCapability")
    server.handle_message({"jsonrpc": "2.0", "id": register_id, "error": {"code": -32000, "message": "rejected"}})
    shutdown = server.handle_message({"jsonrpc": "2.0", "id": 9, "method": "shutdown", "params": {}})
    assert len(shutdown) == 1

