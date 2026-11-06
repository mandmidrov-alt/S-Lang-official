"""JSON-RPC 2.0 adapter and Content-Length framing for S-Lang LSP.

This module is intentionally layered above :mod:`slang.lsp_server`.  The
language server core remains usable without JSON-RPC, sockets, or subprocesses.
The adapter maps standard LSP requests/notifications to the transport-neutral
server and returns JSON-safe JSON-RPC messages.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from .lsp_server import LSPServer


JSONRPC_VERSION = "2.0"
CONTENT_TYPE = "application/vscode-jsonrpc; charset=utf-8"

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class JsonRpcError(Exception):
    """A JSON-RPC error with a standard or application-defined code."""

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


@dataclass(frozen=True)
class JsonRpcMessage:
    """Validated JSON-RPC 2.0 message."""

    payload: Mapping[str, Any]

    @property
    def is_request(self) -> bool:
        return "method" in self.payload and "id" in self.payload

    @property
    def is_notification(self) -> bool:
        return "method" in self.payload and "id" not in self.payload


def _error_payload(request_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    result: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "id": request_id, "error": {"code": code, "message": message}}
    if data is not None:
        result["error"]["data"] = data
    return result


def make_response(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}


def make_notification(method: str, params: Any = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "method": method}
    if params is not None:
        payload["params"] = params
    return payload


def serialize_message(message: Mapping[str, Any]) -> bytes:
    """Serialize one JSON-RPC message using deterministic UTF-8 JSON."""
    payload = json.dumps(message, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return payload.encode("utf-8")


def encode_message(message: Mapping[str, Any]) -> bytes:
    """Encode one JSON-RPC message using LSP Content-Length framing."""
    body = serialize_message(message)
    header = f"Content-Length: {len(body)}\r\nContent-Type: {CONTENT_TYPE}\r\n\r\n".encode("ascii")
    return header + body


class JsonRpcFramer:
    """Incremental Content-Length frame decoder for byte streams."""

    def __init__(self):
        self._buffer = bytearray()

    def feed(self, data: bytes | bytearray | memoryview) -> tuple[dict[str, Any], ...]:
        self._buffer.extend(bytes(data))
        messages: list[dict[str, Any]] = []
        while True:
            separator = self._buffer.find(b"\r\n\r\n")
            if separator < 0:
                break
            header_block = bytes(self._buffer[:separator]).decode("ascii")
            headers: dict[str, str] = {}
            for line in header_block.split("\r\n"):
                if ":" not in line:
                    raise ValueError("invalid LSP message header")
                key, value = line.split(":", 1)
                key = key.strip().lower()
                if key in headers:
                    raise ValueError(f"duplicate LSP message header: {key}")
                headers[key] = value.strip()
            if "content-length" not in headers:
                raise ValueError("missing Content-Length header")
            try:
                length = int(headers["content-length"])
            except ValueError as exc:
                raise ValueError("invalid Content-Length header") from exc
            if length < 0:
                raise ValueError("invalid Content-Length header")
            total = separator + 4 + length
            if len(self._buffer) < total:
                break
            framed = bytes(self._buffer[:total])
            del self._buffer[:total]
            messages.append(decode_message(framed))
        return tuple(messages)


def decode_message(data: bytes | bytearray | memoryview) -> dict[str, Any]:
    """Decode exactly one complete Content-Length framed LSP message."""
    raw = bytes(data)
    separator = raw.find(b"\r\n\r\n")
    if separator < 0:
        raise ValueError("incomplete LSP message headers")
    header_block = raw[:separator].decode("ascii")
    body = raw[separator + 4 :]
    headers: dict[str, str] = {}
    for line in header_block.split("\r\n"):
        if ":" not in line:
            raise ValueError("invalid LSP message header")
        key, value = line.split(":", 1)
        key = key.strip().lower()
        if key in headers:
            raise ValueError(f"duplicate LSP message header: {key}")
        headers[key] = value.strip()
    if "content-length" not in headers:
        raise ValueError("missing Content-Length header")
    try:
        length = int(headers["content-length"])
    except ValueError as exc:
        raise ValueError("invalid Content-Length header") from exc
    if length < 0 or len(body) != length:
        raise ValueError("LSP message body length does not match Content-Length")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid JSON-RPC message body") from exc
    if not isinstance(payload, dict):
        raise ValueError("JSON-RPC message must be an object")
    return payload


class LSPJsonRpcServer:
    """JSON-RPC 2.0/LSP dispatcher backed by :class:`LSPServer`."""

    def __init__(self, server: LSPServer | None = None):
        self.server = server or LSPServer()
        self._exit_requested = False
        self._initialized_notification = False
        self._session_state = "created"
        self._client_capabilities: Mapping[str, Any] = {}
        self._next_server_request_id = 1
        self._pending_server_requests: dict[int, str] = {}
        self._dynamic_watch_registered = False

    @property
    def exit_requested(self) -> bool:
        return self._exit_requested

    @property
    def session_state(self) -> str:
        """Return the JSON-RPC/LSP session lifecycle state."""
        return self._session_state

    def handle_message(self, message: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
        """Dispatch one already-decoded JSON-RPC message.

        A request returns one response, optionally followed by diagnostic
        notifications. A notification returns only outbound notifications.
        """
        try:
            if self._is_response(message):
                return self._handle_response(message)
            request = self._validate(message)
            method = request.payload.get("method")
            params = request.payload.get("params")
            request_id = request.payload.get("id") if request.is_request else None
            outbound = self._dispatch(method, params)
            if request.is_request:
                return (make_response(request_id, outbound[0]), *outbound[1:])
            return outbound
        except JsonRpcError as exc:
            if "id" not in message:
                return ()
            return (_error_payload(message.get("id"), exc.code, exc.message, exc.data),)
        except Exception as exc:
            # Editor requests must remain usable while the user is typing an
            # incomplete or syntactically invalid document. Some semantic
            # features require a complete parse tree; return their protocol
            # empty value instead of surfacing repeated -32603 errors. Keep
            # unexpected failures for unrelated requests visible to the client.
            if "id" not in message:
                return ()
            method = message.get("method")
            error_text = str(exc).lower()
            is_source_parse_failure = any(
                marker in error_text
                for marker in ("unknown syntax", "syntax error", "parse error", "unexpected token", "expected expression")
            )
            if is_source_parse_failure:
                if method == "textDocument/hover":
                    return (make_response(message.get("id"), None),)
                if method in {"textDocument/documentSymbol", "textDocument/inlayHint",
                              "textDocument/documentLink", "textDocument/documentHighlight",
                              "textDocument/references", "textDocument/definition",
                              "textDocument/typeDefinition", "textDocument/implementation",
                              "textDocument/foldingRange", "textDocument/codeAction"}:
                    return (make_response(message.get("id"), []),)
                if method in {"textDocument/semanticTokens/full", "textDocument/semanticTokens/range"}:
                    return (make_response(message.get("id"), {"data": []}),)
            return (_error_payload(message.get("id"), INTERNAL_ERROR, "Internal error", str(exc)),)

    @staticmethod
    def _is_response(message: Mapping[str, Any]) -> bool:
        return isinstance(message, Mapping) and "method" not in message and "id" in message and ("result" in message or "error" in message)

    def _handle_response(self, message: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
        if message.get("jsonrpc") != JSONRPC_VERSION:
            return (_error_payload(message.get("id"), INVALID_REQUEST, "Invalid Request"),)
        request_id = message.get("id")
        if not isinstance(request_id, int) or isinstance(request_id, bool):
            return (_error_payload(request_id, INVALID_REQUEST, "Invalid Request"),)
        kind = self._pending_server_requests.pop(request_id, None)
        if kind is None:
            return ()
        if kind == "workspace/configuration":
            if "error" in message:
                return ()
            result = message.get("result")
            if not isinstance(result, list):
                return ()
            settings = result[0] if result and isinstance(result[0], Mapping) else {}
            publications = self.server.did_change_configuration({"slang": settings})
            return self._publish_notifications(publications)
        if kind == "workspace/applyEdit":
            return ()
        if kind == "client/registerCapability":
            if "error" not in message:
                self._dynamic_watch_registered = True
            return ()
        if kind == "client/unregisterCapability":
            return ()
        return ()

    def _new_server_request_id(self) -> int:
        request_id = self._next_server_request_id
        self._next_server_request_id += 1
        return request_id

    def _client_supports_apply_edit(self) -> bool:
        workspace = self._client_capabilities.get("workspace")
        return isinstance(workspace, Mapping) and workspace.get("applyEdit") is True

    def _workspace_apply_edit_request(self, edit: Mapping[str, Any], *, label: str = "S-Lang quick fix") -> dict[str, Any] | None:
        if not self._client_supports_apply_edit():
            return None
        request_id = self._new_server_request_id()
        self._pending_server_requests[request_id] = "workspace/applyEdit"
        return {
            "jsonrpc": JSONRPC_VERSION,
            "id": request_id,
            "method": "workspace/applyEdit",
            "params": {"edit": dict(edit), "label": label},
        }

    def _client_supports_dynamic_file_watch_registration(self) -> bool:
        workspace = self._client_capabilities.get("workspace")
        if not isinstance(workspace, Mapping):
            return False
        watched = workspace.get("didChangeWatchedFiles")
        return isinstance(watched, Mapping) and watched.get("dynamicRegistration") is True

    def _dynamic_watch_registration(self) -> dict[str, Any] | None:
        if not self._client_supports_dynamic_file_watch_registration():
            return None
        request_id = self._new_server_request_id()
        self._pending_server_requests[request_id] = "client/registerCapability"
        return {
            "jsonrpc": JSONRPC_VERSION,
            "id": request_id,
            "method": "client/registerCapability",
            "params": {
                "registrations": [{
                    "id": "slang-workspace-file-watch",
                    "method": "workspace/didChangeWatchedFiles",
                    "registerOptions": {
                        "watchers": [{"globPattern": "**/*.sl", "kind": 7}],
                    },
                }]
            },
        }


    def _dynamic_watch_unregistration(self) -> dict[str, Any] | None:
        if not self._dynamic_watch_registered:
            return None
        request_id = self._new_server_request_id()
        self._pending_server_requests[request_id] = "client/unregisterCapability"
        self._dynamic_watch_registered = False
        return {
            "jsonrpc": JSONRPC_VERSION,
            "id": request_id,
            "method": "client/unregisterCapability",
            "params": {
                "unregistrations": [{
                    "id": "slang-workspace-file-watch",
                    "method": "workspace/didChangeWatchedFiles",
                }]
            },
        }

    def _configuration_request(self) -> dict[str, Any] | None:
        workspace = self._client_capabilities.get("workspace")
        if not isinstance(workspace, Mapping) or workspace.get("configuration") is not True:
            return None
        request_id = self._new_server_request_id()
        self._pending_server_requests[request_id] = "workspace/configuration"
        scope_uri = self.server.root_uri
        return {
            "jsonrpc": JSONRPC_VERSION,
            "id": request_id,
            "method": "workspace/configuration",
            "params": {"items": [{"scopeUri": scope_uri, "section": "slang"}]},
        }

    def _validate(self, message: Mapping[str, Any]) -> JsonRpcMessage:
        if not isinstance(message, Mapping) or message.get("jsonrpc") != JSONRPC_VERSION:
            raise JsonRpcError(INVALID_REQUEST, "Invalid Request")
        method = message.get("method")
        if not isinstance(method, str) or not method:
            raise JsonRpcError(INVALID_REQUEST, "Invalid Request")
        if "id" in message and isinstance(message["id"], (dict, list, bool)):
            raise JsonRpcError(INVALID_REQUEST, "Invalid Request")
        if "params" in message and not isinstance(message["params"], (Mapping, list, tuple)):
            raise JsonRpcError(INVALID_REQUEST, "Invalid Request")
        return JsonRpcMessage(message)

    def _require_params(self, params: Any) -> Mapping[str, Any]:
        if params is None:
            return {}
        if not isinstance(params, Mapping):
            raise JsonRpcError(INVALID_PARAMS, "Invalid params")
        return params

    def _require_initialized(self, method: str) -> None:
        if method == "initialize":
            if self._session_state != "created":
                raise JsonRpcError(INVALID_REQUEST, "Server has already been initialized")
            return
        if method == "exit":
            return
        if self._session_state == "created" or not self.server.initialized:
            raise JsonRpcError(INVALID_REQUEST, "Server is not initialized")
        if self._session_state == "shutdown" and method != "exit":
            raise JsonRpcError(INVALID_REQUEST, "Server is shutting down")

    def _dispatch(self, method: str, params: Any) -> tuple[dict[str, Any], ...]:
        self._require_initialized(method)
        if method == "initialize":
            p = self._require_params(params)
            self._client_capabilities = p.get("capabilities") if isinstance(p.get("capabilities"), Mapping) else {}
            result = self.server.initialize(
                client_capabilities=self._client_capabilities,
                root_uri=p.get("rootUri"),
                workspace_folders=p.get("workspaceFolders"),
            )
            self._session_state = "initialized"
            return (result,)
        if method == "initialized":
            if self._session_state != "initialized":
                raise JsonRpcError(INVALID_REQUEST, "Server is not awaiting initialized notification")
            self._initialized_notification = True
            outbound: list[dict[str, Any]] = []
            registration = self._dynamic_watch_registration()
            if registration is not None:
                outbound.append(registration)
            request = self._configuration_request()
            if request is not None:
                outbound.append(request)
            return tuple(outbound)
        if method == "textDocument/hover":
            p = self._require_params(params)
            doc = self._document(p)
            position = p.get("position")
            if not isinstance(position, Mapping) or not isinstance(position.get("line"), int) or not isinstance(position.get("character"), int):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params: position is required")
            return (self.server.hover(doc["uri"], position["line"], position["character"]),)
        if method == "textDocument/semanticTokens/full":
            p = self._require_params(params)
            doc = self._document(p)
            if isinstance(p.get("previousResultId"), str):
                return (self.server.semantic_tokens_delta(doc["uri"], p["previousResultId"]),)
            return (self.server.semantic_tokens(doc["uri"]),)
        if method == "textDocument/semanticTokens/range":
            p = self._require_params(params)
            doc = self._document(p)
            rng = p.get("range")
            if not isinstance(rng, Mapping):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params: range is required")
            start = rng.get("start")
            end = rng.get("end")
            if (not isinstance(start, Mapping) or not isinstance(end, Mapping) or
                    not isinstance(start.get("line"), int) or not isinstance(start.get("character"), int) or
                    not isinstance(end.get("line"), int) or not isinstance(end.get("character"), int)):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params: range positions are required")
            return (self.server.semantic_tokens_range(doc["uri"], start["line"], end["line"], start["character"], end["character"]),)
        if method == "textDocument/inlayHint":
            p = self._require_params(params)
            doc = self._document(p)
            rng = p.get("range")
            if not isinstance(rng, Mapping):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params: range is required")
            start = rng.get("start")
            end = rng.get("end")
            if (not isinstance(start, Mapping) or not isinstance(end, Mapping) or
                    not isinstance(start.get("line"), int) or not isinstance(start.get("character"), int) or
                    not isinstance(end.get("line"), int) or not isinstance(end.get("character"), int)):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params: range positions are required")
            return (list(self.server.inlay_hints(doc["uri"], range_start=dict(start), range_end=dict(end))),)
        if method == "textDocument/documentLink":
            p = self._require_params(params)
            doc = self._document(p)
            return (list(self.server.document_links(doc["uri"])),)
        if method == "textDocument/documentHighlight":
            p = self._require_params(params)
            doc = self._document(p)
            position = p.get("position")
            if not isinstance(position, Mapping) or not isinstance(position.get("line"), int) or not isinstance(position.get("character"), int):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params: position is required")
            return (list(self.server.document_highlight(doc["uri"], position["line"], position["character"])),)
        if method == "textDocument/prepareRename":
            p = self._require_params(params)
            doc = self._document(p)
            position = p.get("position")
            if not isinstance(position, Mapping) or not isinstance(position.get("line"), int) or not isinstance(position.get("character"), int):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params: position is required")
            return (self.server.prepare_rename(doc["uri"], position["line"], position["character"]),)
        if method == "textDocument/rename":
            p = self._require_params(params)
            doc = self._document(p)
            position = p.get("position")
            new_name = p.get("newName")
            if not isinstance(position, Mapping) or not isinstance(position.get("line"), int) or not isinstance(position.get("character"), int) or not isinstance(new_name, str):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params: position and newName are required")
            return (self.server.rename(doc["uri"], position["line"], position["character"], new_name),)
        if method == "textDocument/codeAction":
            p = self._require_params(params)
            doc = self._document(p)
            context = p.get("context", {})
            if not isinstance(context, Mapping):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params: context must be an object")
            return (list(self.server.code_actions(doc["uri"], diagnostics=context.get("diagnostics"))),)
        if method == "workspace/executeCommand":
            p = self._require_params(params)
            command = p.get("command")
            arguments = p.get("arguments", [])
            if not isinstance(command, str) or not isinstance(arguments, list):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params: command and arguments are required")
            try:
                edit = self.server.execute_command(command, arguments)
            except KeyError as exc:
                raise JsonRpcError(METHOD_NOT_FOUND, str(exc)) from exc
            except ValueError as exc:
                raise JsonRpcError(INVALID_PARAMS, str(exc)) from exc
            request = self._workspace_apply_edit_request(edit, label="S-Lang quick fix") if isinstance(edit, Mapping) else None
            return (edit, request) if request is not None else (edit,)
        if method == "textDocument/signatureHelp":
            p = self._require_params(params)
            doc = self._document(p)
            position = p.get("position")
            if not isinstance(position, Mapping) or not isinstance(position.get("line"), int) or not isinstance(position.get("character"), int):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params: position is required")
            return (self.server.signature_help(doc["uri"], position["line"], position["character"]),)
        if method == "textDocument/completion":
            p = self._require_params(params)
            doc = self._document(p)
            position = p.get("position")
            if not isinstance(position, Mapping) or not isinstance(position.get("line"), int) or not isinstance(position.get("character"), int):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params: position is required")
            items = self.server.completion(doc["uri"], position["line"], position["character"])
            return ({"isIncomplete": False, "items": list(items)},)
        if method == "textDocument/documentSymbol":
            p = self._require_params(params)
            doc = self._document(p)
            return (list(self.server.document_symbols(doc["uri"])),)
        if method == "textDocument/references":
            p = self._require_params(params)
            doc = self._document(p)
            position = p.get("position")
            if not isinstance(position, Mapping) or not isinstance(position.get("line"), int) or not isinstance(position.get("character"), int):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params: position is required")
            context = p.get("context", {})
            if not isinstance(context, Mapping):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params: context must be an object")
            include_declaration = context.get("includeDeclaration", True) is not False
            return (list(self.server.references(doc["uri"], position["line"], position["character"], include_declaration)),)
        if method == "workspace/symbol":
            p = self._require_params(params)
            query = p.get("query", "")
            if not isinstance(query, str):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params: query must be a string")
            return (list(self.server.workspace_symbols(query)),)
        if method == "textDocument/definition":
            p = self._require_params(params)
            doc = self._document(p)
            position = p.get("position")
            if not isinstance(position, Mapping) or not isinstance(position.get("line"), int) or not isinstance(position.get("character"), int):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params: position is required")
            return (list(self.server.definition(doc["uri"], position["line"], position["character"])),)
        if method == "workspace/didChangeConfiguration":
            p = self._require_params(params)
            settings = p.get("settings", {})
            publications = self.server.did_change_configuration(settings)
            return self._publish_notifications(publications)
        if method == "workspace/didCreateFiles":
            p = self._require_params(params)
            files = p.get("files")
            if not isinstance(files, list):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params: files must be an array")
            publications = self.server.did_create_publications(files)
            return self._publish_notifications(publications)
        if method == "workspace/didRenameFiles":
            p = self._require_params(params)
            files = p.get("files")
            if not isinstance(files, list):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params: files must be an array")
            publications = self.server.did_rename_publications(files)
            return self._publish_notifications(publications)
        if method == "workspace/didDeleteFiles":
            p = self._require_params(params)
            files = p.get("files")
            if not isinstance(files, list):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params: files must be an array")
            publications = self.server.did_delete_publications(files)
            return self._publish_notifications(publications)
        if method == "workspace/didChangeWatchedFiles":
            p = self._require_params(params)
            changes = p.get("changes")
            if not isinstance(changes, list):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params: changes must be an array")
            publications = self.server.did_change_watched_files(changes)
            return self._publish_notifications(publications)
        if method == "workspace/didChangeWorkspaceFolders":
            p = self._require_params(params)
            event = p.get("event")
            if not isinstance(event, Mapping):
                raise JsonRpcError(INVALID_PARAMS, "Invalid params: event is required")
            self.server.did_change_workspace_folders(event)
            return ()
        if method == "shutdown":
            if self._session_state != "initialized":
                raise JsonRpcError(INVALID_REQUEST, "Server is not initialized")
            self.server.shutdown()
            self._session_state = "shutdown"
            unregister = self._dynamic_watch_unregistration()
            return (None, unregister) if unregister is not None else (None,)
        if method == "exit":
            self._exit_requested = True
            return ()
        if method == "textDocument/didOpen":
            p = self._require_params(params)
            doc = self._document(p)
            return self._publish_notifications(self.server.did_open_publications(doc["uri"], doc["text"], version=doc.get("version")))
        if method == "textDocument/didChange":
            p = self._require_params(params)
            doc = self._document(p)
            changes = p.get("contentChanges")
            if not isinstance(changes, list) or not changes:
                raise JsonRpcError(INVALID_PARAMS, "Invalid params: contentChanges must be a non-empty array")
            if len(changes) == 1 and isinstance(changes[0], Mapping) and "range" not in changes[0]:
                text_or_changes: Any = changes[0].get("text")
                if not isinstance(text_or_changes, str):
                    raise JsonRpcError(INVALID_PARAMS, "Invalid params: contentChanges[0].text is required")
            else:
                text_or_changes = changes
            return self._publish_notifications(self.server.did_change_publications(doc["uri"], text_or_changes, version=doc.get("version")))
        if method == "textDocument/didSave":
            p = self._require_params(params)
            doc = self._document(p)
            return self._publish_notifications(self._single_publication(self.server.did_save(doc["uri"], text=doc.get("text"))))
        if method == "textDocument/didClose":
            p = self._require_params(params)
            doc = self._document(p)
            return self._publish_notifications(self._single_publication(self.server.did_close(doc["uri"])))
        raise JsonRpcError(METHOD_NOT_FOUND, "Method not found", {"method": method})

    @staticmethod
    def _document(params: Mapping[str, Any]) -> Mapping[str, Any]:
        document = params.get("textDocument")
        if not isinstance(document, Mapping) or not isinstance(document.get("uri"), str):
            raise JsonRpcError(INVALID_PARAMS, "Invalid params: textDocument.uri is required")
        return document

    @staticmethod
    def _publish_notifications(publications: tuple[dict, ...]) -> tuple[dict, ...]:
        return tuple(make_notification("textDocument/publishDiagnostics", publication) for publication in publications)

    @staticmethod
    def _single_publication(publication: dict) -> tuple[dict, ...]:
        return (publication,)


__all__ = [
    "CONTENT_TYPE", "JSONRPC_VERSION", "PARSE_ERROR", "INVALID_REQUEST", "METHOD_NOT_FOUND",
    "INVALID_PARAMS", "INTERNAL_ERROR", "JsonRpcError", "JsonRpcMessage", "JsonRpcFramer", "LSPJsonRpcServer",
    "make_response", "make_notification", "serialize_message", "encode_message", "decode_message",
]
