"""Minimal RFC 6455 WebSocket pieces for the Xairex browser bridge (D43).

Only what the bridge needs: the server-side handshake, masked client frames,
unmasked server frames, ping/pong/close and message aggregation. Standard
library only — the bridge carries small JSON documents, so the 1 MiB cap is
generous. Reference: RFC 6455 (https://www.rfc-editor.org/rfc/rfc6455).
"""

from __future__ import annotations

import base64
import hashlib
import os
import struct
from dataclasses import dataclass

#: RFC 6455 magic GUID appended to Sec-WebSocket-Key before hashing.
_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

OP_CONTINUATION = 0x0
OP_TEXT = 0x1
OP_BINARY = 0x2
OP_CLOSE = 0x8
OP_PING = 0x9
OP_PONG = 0xA

#: Refuse single messages larger than this (bytes). The bridge is JSON-only.
MAX_MESSAGE_BYTES = 1 << 20


class ProtocolError(RuntimeError):
    """The peer sent something that is not valid WebSocket data."""


def accept_key(client_key: str) -> str:
    """RFC 6455 ``Sec-WebSocket-Accept`` value for a client's ``Sec-WebSocket-Key``."""
    digest = hashlib.sha1((client_key.strip() + _WS_GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def encode_frame(payload: bytes, opcode: int = OP_TEXT, *, fin: bool = True, mask: bool = False) -> bytes:
    """One WebSocket frame.

    Server-to-client frames are unmasked; client-to-server frames must be
    masked (``mask=True``), exactly like a browser sends them.
    """
    header = bytearray()
    header.append((0x80 if fin else 0x00) | (opcode & 0x0F))
    length = len(payload)
    mask_bit = 0x80 if mask else 0x00
    if length < 126:
        header.append(mask_bit | length)
    elif length < (1 << 16):
        header.append(mask_bit | 126)
        header += struct.pack("!H", length)
    else:
        header.append(mask_bit | 127)
        header += struct.pack("!Q", length)
    if not mask:
        return bytes(header) + payload
    key = os.urandom(4)
    masked = bytes(byte ^ key[index % 4] for index, byte in enumerate(payload))
    return bytes(header) + key + masked


@dataclass(frozen=True)
class Frame:
    """One decoded WebSocket frame."""

    fin: bool
    opcode: int
    payload: bytes


def decode_frame(buffer: bytearray) -> Frame | None:
    """Pop one complete frame off *buffer*; ``None`` when more bytes are needed.

    The consumed bytes are removed from *buffer*; masked payloads are unmasked
    in place. Raises :class:`ProtocolError` for oversized frames.
    """
    if len(buffer) < 2:
        return None
    first, second = buffer[0], buffer[1]
    fin = bool(first & 0x80)
    opcode = first & 0x0F
    masked = bool(second & 0x80)
    length = second & 0x7F
    offset = 2
    if length == 126:
        if len(buffer) < offset + 2:
            return None
        (length,) = struct.unpack_from("!H", buffer, offset)
        offset += 2
    elif length == 127:
        if len(buffer) < offset + 8:
            return None
        (length,) = struct.unpack_from("!Q", buffer, offset)
        offset += 8
    if length > MAX_MESSAGE_BYTES:
        raise ProtocolError(f"frame too large: {length} bytes")
    key = b""
    if masked:
        if len(buffer) < offset + 4:
            return None
        key = bytes(buffer[offset : offset + 4])
        offset += 4
    if len(buffer) < offset + length:
        return None
    payload = bytes(buffer[offset : offset + length])
    del buffer[: offset + length]
    if masked:
        payload = bytes(byte ^ key[index % 4] for index, byte in enumerate(payload))
    return Frame(fin, opcode, payload)


def handshake_response(request: bytes) -> tuple[str, bytes]:
    """Parse a client HTTP upgrade request.

    Returns ``(client_key, response_bytes)`` on success. Raises
    :class:`ProtocolError` with a short reason when the request is not a valid
    WebSocket upgrade.
    """
    try:
        head = request.decode("latin-1")
    except UnicodeDecodeError as exc:  # pragma: no cover - latin-1 never fails
        raise ProtocolError("unreadable handshake") from exc
    lines = head.split("\r\n")
    if not lines or not lines[0].startswith("GET "):
        raise ProtocolError("expected a GET upgrade request")
    headers: dict[str, str] = {}
    for line in lines[1:]:
        name, _, value = line.partition(":")
        if name:
            headers[name.strip().lower()] = value.strip()
    key = headers.get("sec-websocket-key", "")
    if not key:
        raise ProtocolError("missing Sec-WebSocket-Key")
    if headers.get("upgrade", "").lower() != "websocket":
        raise ProtocolError("missing Upgrade: websocket")
    response = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept_key(key)}\r\n"
        "\r\n"
    ).encode("ascii")
    return key, response


def handshake_request(host: str, port: int, path: str = "/xairex", origin: str = "") -> bytes:
    """A client upgrade request (used by the test/probe client, not the app)."""
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    lines = [
        f"GET {path} HTTP/1.1",
        f"Host: {host}:{port}",
        "Upgrade: websocket",
        "Connection: Upgrade",
        f"Sec-WebSocket-Key: {key}",
        "Sec-WebSocket-Version: 13",
    ]
    if origin:
        lines.append(f"Origin: {origin}")
    return ("\r\n".join(lines) + "\r\n\r\n").encode("ascii")
