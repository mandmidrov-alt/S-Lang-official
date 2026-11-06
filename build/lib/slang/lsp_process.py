"""Stream-oriented JSON-RPC process loop for the S-Lang Language Server.

The process layer sits above :mod:`slang.lsp_jsonrpc`.  It owns byte-stream
framing and server lifecycle, while the compiler and transport-neutral LSP
core remain independent of process management and concrete I/O.
"""

from __future__ import annotations

from typing import BinaryIO, Callable

from .lsp_jsonrpc import (
    INTERNAL_ERROR,
    PARSE_ERROR,
    JsonRpcFramer,
    LSPJsonRpcServer,
    _error_payload,
    encode_message,
)


class LSPProcess:
    """Incremental LSP server process adapter.

    ``feed()`` is the non-blocking primitive for embedding the server in an
    application.  ``serve()`` provides a small synchronous loop for stdin /
    stdout-like binary streams.
    """

    def __init__(self, rpc: LSPJsonRpcServer | None = None, *, chunk_size: int = 65536):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        self.rpc = rpc or LSPJsonRpcServer()
        self.framer = JsonRpcFramer()
        self.chunk_size = chunk_size
        self._stopped = False

    @property
    def stopped(self) -> bool:
        return self._stopped or self.rpc.exit_requested

    def feed(self, data: bytes | bytearray | memoryview) -> bytes:
        """Consume zero or more framed messages and return encoded replies."""
        if self.stopped:
            return b""
        try:
            messages = self.framer.feed(data)
        except ValueError as exc:
            # The frame has been consumed by JsonRpcFramer before decoding;
            # emit the standard parse error and keep the process alive.
            self._stopped = False
            return encode_message(_error_payload(None, PARSE_ERROR, "Parse error", str(exc)))

        output = bytearray()
        for message in messages:
            for response in self.rpc.handle_message(message):
                output.extend(encode_message(response))
            if self.rpc.exit_requested:
                self._stopped = True
                break
        return bytes(output)

    def serve(
        self,
        reader: BinaryIO,
        writer: BinaryIO,
        *,
        on_output: Callable[[bytes], None] | None = None,
    ) -> None:
        """Run until EOF or an LSP ``exit`` notification is received."""
        while not self.stopped:
            # BufferedReader.read(n) may wait for more data on some pipe
            # implementations. Prefer read1() so a short LSP frame sent by
            # an editor is processed as soon as bytes are available.
            read_once = getattr(reader, "read1", None)
            if callable(read_once):
                chunk = read_once(self.chunk_size)
            else:
                chunk = reader.read(self.chunk_size)
            if not chunk:
                self._stopped = True
                break
            output = self.feed(chunk)
            if output:
                writer.write(output)
                flush = getattr(writer, "flush", None)
                if callable(flush):
                    flush()
                if on_output is not None:
                    on_output(output)


def run_lsp_server(
    reader: BinaryIO,
    writer: BinaryIO,
    *,
    rpc: LSPJsonRpcServer | None = None,
    chunk_size: int = 65536,
) -> LSPProcess:
    """Run an LSP process loop over binary reader/writer streams."""
    process = LSPProcess(rpc, chunk_size=chunk_size)
    process.serve(reader, writer)
    return process


__all__ = ["LSPProcess", "run_lsp_server"]
