import io

from slang import LSPProcess, LSPJsonRpcServer, encode_message


def decode_frames(data):
    from slang import JsonRpcFramer
    return JsonRpcFramer().feed(data)


def test_feed_handles_initialize_and_shutdown():
    process = LSPProcess()
    output = process.feed(encode_message({
        "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}
    }))
    messages = decode_frames(output)
    assert messages[0]["id"] == 1
    assert messages[0]["result"]["serverInfo"]["version"] == "1.0"
    output = process.feed(encode_message({"jsonrpc": "2.0", "id": 2, "method": "shutdown"}))
    assert decode_frames(output) == ({"jsonrpc": "2.0", "id": 2, "result": None},)


def test_feed_emits_diagnostics_and_stops_after_exit():
    process = LSPProcess()
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {
            "textDocument": {"uri": "file:///tmp/example.sl", "version": 1, "text": 'let x = 1 + "text"\n'}
        }},
        {"jsonrpc": "2.0", "method": "exit"},
    ]
    wire = b"".join(encode_message(item) for item in messages)
    output = process.feed(wire)
    decoded = decode_frames(output)
    assert decoded[0]["id"] == 1
    assert decoded[1]["method"] == "textDocument/publishDiagnostics"
    assert decoded[1]["params"]["diagnostics"][0]["code"] == "E2000"
    assert process.stopped is True
    assert process.feed(encode_message({"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {}})) == b""


def test_partial_stream_is_buffered_across_reads():
    process = LSPProcess()
    message = encode_message({"jsonrpc": "2.0", "id": 7, "method": "initialize", "params": {}})
    assert process.feed(message[:5]) == b""
    assert decode_frames(process.feed(message[5:]))[0]["id"] == 7


def test_serve_reads_until_eof_and_writes_responses():
    incoming = b"".join([
        encode_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
        encode_message({"jsonrpc": "2.0", "id": 2, "method": "shutdown"}),
        encode_message({"jsonrpc": "2.0", "method": "exit"}),
    ])
    reader = io.BytesIO(incoming)
    writer = io.BytesIO()
    process = LSPProcess(LSPJsonRpcServer(), chunk_size=13)
    process.serve(reader, writer)
    messages = decode_frames(writer.getvalue())
    assert [m["id"] for m in messages] == [1, 2]
    assert process.stopped is True


def test_parse_error_is_returned_and_server_can_continue():
    process = LSPProcess()
    malformed = b"Content-Length: 5\r\n\r\nxxxxx"
    output = process.feed(malformed)
    response = decode_frames(output)[0]
    assert response["id"] is None
    assert response["error"]["code"] == -32700
    assert process.feed(encode_message({"jsonrpc": "2.0", "id": 3, "method": "initialize", "params": {}}))


class Read1OnlyReader:
    """Pipe-like test reader that requires the non-buffer-filling read path."""

    def __init__(self, data):
        self.data = data

    def read1(self, size=-1):
        if not self.data:
            return b""
        chunk, self.data = self.data[:size], self.data[size:]
        return chunk

    def read(self, size=-1):
        raise AssertionError("serve() should prefer read1() when available")


def test_serve_prefers_read1_for_pipe_like_readers():
    incoming = b"".join([
        encode_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
        encode_message({"jsonrpc": "2.0", "id": 2, "method": "shutdown"}),
        encode_message({"jsonrpc": "2.0", "method": "exit"}),
    ])
    reader = Read1OnlyReader(incoming)
    writer = io.BytesIO()
    process = LSPProcess(LSPJsonRpcServer())
    process.serve(reader, writer)
    messages = decode_frames(writer.getvalue())
    assert [message["id"] for message in messages] == [1, 2]
    assert process.stopped is True
