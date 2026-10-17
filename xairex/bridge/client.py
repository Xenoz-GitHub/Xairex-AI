"""Blocking WebSocket client for the bridge protocol (tests, probes, debugging).

The real browser client is ``extension/background.js``; this module implements
the same wire behavior (masked frames, JSON messages, ``chrome-extension://``
origin) so the whole host side can be exercised offline and in live smoke
probes without a browser.
"""

from __future__ import annotations

import json
import socket
import time
from typing import Any, Self

from xairex.bridge.wsproto import (
    MAX_MESSAGE_BYTES,
    OP_CLOSE,
    OP_PING,
    OP_PONG,
    OP_TEXT,
    ProtocolError,
    decode_frame,
    encode_frame,
    handshake_request,
)

#: Origin a browser extension sends; the server accepts only chrome/moz-extension origins.
DEFAULT_ORIGIN = "chrome-extension://xairex-bridge-probe"


class BridgeClientError(RuntimeError):
    """The bridge connection failed or the peer misbehaved."""


class BridgeWebSocketClient:
    """Small RFC 6455 client: connect, send JSON, wait for JSON."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8769, *, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._buffer = bytearray()

    # ------------------------------------------------------------------ setup

    def connect(self, *, origin: str = DEFAULT_ORIGIN, path: str = "/xairex") -> None:
        """TCP connect + WebSocket upgrade handshake."""
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        sock.settimeout(self.timeout)
        try:
            sock.sendall(handshake_request(self.host, self.port, path=path, origin=origin))
            head = b""
            while b"\r\n\r\n" not in head:
                chunk = sock.recv(4096)
                if not chunk:
                    raise BridgeClientError("server closed during handshake")
                head += chunk
            status = head.split(b"\r\n", 1)[0].decode("latin-1")
            if "101" not in status:
                raise BridgeClientError(f"handshake rejected: {status}")
            leftover = head.split(b"\r\n\r\n", 1)[1]
            self._buffer += leftover
        except OSError as exc:
            sock.close()
            raise BridgeClientError(str(exc)) from exc
        self._sock = sock

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.sendall(encode_frame(b"", OP_CLOSE, mask=True))
            except OSError:
                pass
            self._sock.close()
            self._sock = None

    def __enter__(self) -> Self:
        self.connect()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ wire

    def send_json(self, payload: dict[str, Any]) -> None:
        if self._sock is None:
            raise BridgeClientError("not connected")
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._sock.sendall(encode_frame(data, OP_TEXT, mask=True))

    def wait_json(self, *, timeout: float | None = None) -> dict[str, Any]:
        """Next JSON message; answers pings; skips keepalive text; raises on close."""
        if self._sock is None:
            raise BridgeClientError("not connected")
        deadline = time.monotonic() + (timeout if timeout is not None else self.timeout)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("no message within the deadline")
            self._sock.settimeout(max(remaining, 0.05))
            try:
                chunk = self._sock.recv(65536)
            except TimeoutError:
                continue
            except OSError as exc:
                raise BridgeClientError(str(exc)) from exc
            if not chunk:
                raise BridgeClientError("connection closed")
            self._buffer += chunk
            while True:
                frame = decode_frame(self._buffer)
                if frame is None:
                    break
                if frame.opcode == OP_PING:
                    self._sock.sendall(encode_frame(frame.payload, OP_PONG, mask=True))
                    continue
                if frame.opcode == OP_PONG:
                    continue
                if frame.opcode == OP_CLOSE:
                    raise BridgeClientError("server closed the connection")
                if frame.opcode != OP_TEXT or not frame.fin:
                    continue
                if len(frame.payload) > MAX_MESSAGE_BYTES:  # pragma: no cover - decoder cap
                    raise ProtocolError("message too large")
                try:
                    message = json.loads(frame.payload.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue  # keepalive / junk
                if isinstance(message, dict):
                    return message

    def wait_command(self, *, name: str | None = None, timeout: float | None = None) -> dict[str, Any]:
        """Wait for a ``command`` message (optionally of one name)."""
        deadline = time.monotonic() + (timeout if timeout is not None else self.timeout)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("no command within the deadline")
            message = self.wait_json(timeout=remaining)
            if message.get("type") == "command" and (name is None or message.get("name") == name):
                return message

    def hello(self, **extra: Any) -> None:
        """Register as a client (the server drops unregistered connections)."""
        payload: dict[str, Any] = {"v": 1, "type": "hello", "client": "xairex-bridge", "ext_version": "test"}
        payload.update(extra)
        self.send_json(payload)

    def send_event(self, event: dict[str, Any]) -> None:
        self.send_json({"v": 1, "type": "event", "event": event})

    def reply(self, command_id: str, *, ok: bool = True, data: dict[str, Any] | None = None, error: str | None = None) -> None:
        self.send_json({"v": 1, "type": "result", "id": command_id, "ok": ok, "data": data or {}, "error": error})
