"""Loopback WebSocket bridge between Xairex and the browser extension (G23, D42/D43).

The Chrome/Edge extension (``extension/`` in the repo) connects to
``ws://127.0.0.1:<port>`` and streams small JSON events: browsing activity,
new-message observations and unread counters. The bridge:

* persists every event through :class:`~xairex.bridge.store.ActivityStore`
  (hourly segments, auto-cycled after ``bridge.retention_hours`` — default 7 h),
* keeps a live unread/message picture for the ``browser_activity`` and
  ``browser_command`` tools,
* relays commands (YouTube control, tab list) to the extension and awaits the
  typed result with a deadline,
* queues short spoken "new message" announcements for the GUI.

Security posture: binds ``127.0.0.1`` only, accepts upgrades from extension
origins only (``chrome-extension://`` / ``moz-extension://``), drops clients
that do not say ``hello`` within a few seconds, and never executes anything it
receives — the only writable effect is appending to the local activity log.
"""

from __future__ import annotations

import json
import logging
import socket
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from typing import Any

from xairex.bridge.store import ActivityStore, normalize_event
from xairex.bridge.wsproto import (
    OP_CLOSE,
    OP_PING,
    OP_PONG,
    OP_TEXT,
    ProtocolError,
    decode_frame,
    encode_frame,
    handshake_response,
)

logger = logging.getLogger("xairex.bridge")

#: How long a fresh connection has to send ``hello`` before it is dropped.
HELLO_TIMEOUT_SECONDS = 10.0

#: Maximum simultaneous extension connections (personal use: 1 is normal).
MAX_CLIENTS = 4

#: Per-platform announcement cooldowns (seconds) so a busy chat is not noisy.
_MESSAGE_ANNOUNCE_EVERY = 20.0
_UNREAD_ANNOUNCE_EVERY = 120.0

#: A generic "something new" note waits this long before it is handed out: if a
#: specific message observation (with a sender) arrives meanwhile, it is
#: dropped — the owner hears the informative note, not both.
_PENDING_UNREAD_GRACE_SECONDS = 4.0

_PLATFORM_LABELS = {
    "facebook": "Facebook",
    "messenger": "Messenger",
    "instagram": "Instagram",
    "discord": "Discord",
    "youtube": "YouTube",
    "web": "the browser",
}


def _label(platform: str) -> str:
    return _PLATFORM_LABELS.get(platform, platform.title() or "the browser")


class _Pending:
    __slots__ = ("box", "event")

    def __init__(self) -> None:
        self.event = threading.Event()
        self.box: dict[str, Any] = {}


class _ClientConnection:
    """One accepted WebSocket connection from the extension."""

    def __init__(self, server: BridgeServer, sock: socket.socket, address: tuple[str, int]) -> None:
        self.server = server
        self.sock = sock
        self.address = address
        self.id = uuid.uuid4().hex[:8]
        self.buffer = bytearray()
        self.registered = False
        self.info: dict[str, Any] = {}
        self.closed = threading.Event()
        self._send_lock = threading.Lock()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------ wire

    def send_json(self, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(encode_frame(data, OP_TEXT))

    def _send_bytes(self, data: bytes) -> None:
        with self._send_lock:
            self.sock.sendall(data)

    def close(self) -> None:
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass
        self.closed.set()

    # ------------------------------------------------------------------ loop

    def start(self) -> None:
        self._thread = threading.Thread(target=self._read_loop, name=f"xairex-bridge-{self.id}", daemon=True)
        self._thread.start()

    def join(self, timeout: float) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    def _read_loop(self) -> None:
        self.sock.settimeout(0.5)
        registration_deadline = time.monotonic() + HELLO_TIMEOUT_SECONDS
        try:
            while not self.server.stopping.is_set() and not self.closed.is_set():
                try:
                    chunk = self.sock.recv(65536)
                except TimeoutError:
                    if not self.registered and time.monotonic() > registration_deadline:
                        logger.info("bridge: dropping client %s — no hello within %.0fs", self.id, HELLO_TIMEOUT_SECONDS)
                        break
                    continue
                except OSError:
                    break
                if not chunk:
                    break
                self.buffer += chunk
                try:
                    keep_going = self._drain_frames()
                except ProtocolError as exc:
                    logger.debug("bridge: client %s protocol error: %s", self.id, exc)
                    break
                if not keep_going:
                    break
        finally:
            self.close()
            self.server._forget_client(self)

    def _drain_frames(self) -> bool:
        """Handle every complete frame in the buffer; False = close the connection."""
        while True:
            frame = decode_frame(self.buffer)
            if frame is None:
                return True
            if frame.opcode == OP_PING:
                self._send_bytes(encode_frame(frame.payload, OP_PONG))
            elif frame.opcode == OP_PONG:
                continue
            elif frame.opcode == OP_CLOSE:
                return False
            elif frame.opcode == OP_TEXT and frame.fin:
                self._handle_text(frame.payload)
        # unreachable — decode_frame returns None to end the loop

    def _handle_text(self, payload: bytes) -> None:
        try:
            message = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return  # keepalive text or junk — ignore, same as the reference sample
        if not isinstance(message, dict):
            return
        self.server._handle_message(self, message)


class BridgeServer:
    """Owns the loopback listener, the extension connections and the event store."""

    def __init__(
        self,
        settings: Any,
        *,
        store: ActivityStore | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.settings = settings
        self._clock = clock
        self.store = store or ActivityStore(
            settings.resolve_path(settings.bridge.log_dir),
            retention_hours=settings.bridge.retention_hours,
            clock=clock,
        )
        self._lock = threading.RLock()
        self._listener: socket.socket | None = None
        self._accept_thread: threading.Thread | None = None
        self.stopping = threading.Event()
        self._clients: list[_ClientConnection] = []
        self._port = 0
        #: Why the last start() refused to listen ("already-served" | "bind-failed"),
        #: so the UI and tools can say it plainly (live 2026-10-17: a second
        #: window shared the port on Windows and stole the extension link).
        self.refused_reason: str | None = None
        self._pending: dict[str, _Pending] = {}
        self._announcements: deque[dict[str, Any]] = deque(maxlen=100)
        self._pending_unread: dict[str, dict[str, Any]] = {}
        self._unread: dict[str, dict[str, Any]] = {}
        self._last_announce: dict[str, float] = {}
        self._last_event_ms: int = 0
        self._event_count = 0
        self._platform_toggles: dict[str, Any] = {}

    # ----------------------------------------------------------------- states

    @property
    def running(self) -> bool:
        return self._listener is not None and not self.stopping.is_set()

    @property
    def port(self) -> int:
        return self._port

    @property
    def connected(self) -> bool:
        return any(client.registered and not client.closed.is_set() for client in self._clients)

    # -------------------------------------------------------------- lifecycle

    def start(self) -> bool:
        """Bind the loopback listener; False when disabled or the port is taken.

        A port that already answers is left alone: on Windows two sockets can
        bind the same port via SO_REUSEADDR and silently split new connections
        (observed live 2026-10-17: a second Xairex window captured the browser
        extension from the running one), so the first listener keeps the port.
        """
        if not getattr(self.settings.bridge, "enabled", False):
            logger.debug("bridge: disabled in settings")
            return False
        with self._lock:
            if self.running:
                return True
            port = int(self.settings.bridge.port)
            if port and self._port_answered(port):
                self.refused_reason = "already-served"
                logger.warning(
                    "bridge: 127.0.0.1:%s is already served by another process "
                    "(another Xairex window?) — this instance runs without the browser bridge",
                    port,
                )
                return False
            self.refused_reason = None
            family = socket.AF_INET
            listener = socket.socket(family, socket.SOCK_STREAM)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                listener.bind(("127.0.0.1", port))
                listener.listen(4)
            except OSError as exc:
                listener.close()
                self.refused_reason = "bind-failed"
                logger.error("bridge: cannot listen on 127.0.0.1:%s (%s)", port, exc)
                return False
            listener.settimeout(0.5)
            self._listener = listener
            self._port = listener.getsockname()[1]
            self.stopping.clear()
            self._accept_thread = threading.Thread(target=self._accept_loop, name="xairex-bridge-accept", daemon=True)
            self._accept_thread.start()
            logger.info("bridge: listening on 127.0.0.1:%s", self._port)
            return True

    @staticmethod
    def _port_answered(port: int) -> bool:
        """True when something already accepts connections on 127.0.0.1:port."""
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.settimeout(0.3)
        try:
            probe.connect(("127.0.0.1", port))
        except OSError:
            return False
        finally:
            probe.close()
        return True

    def stop(self) -> None:
        """Close the listener and every client (idempotent, quick)."""
        with self._lock:
            if self._listener is None:
                return
            self.stopping.set()
            listener, self._listener = self._listener, None
            clients = list(self._clients)
        try:
            listener.close()
        except OSError:
            pass
        for client in clients:
            client.close()
        if self._accept_thread is not None:
            self._accept_thread.join(timeout=1.0)
            self._accept_thread = None
        for client in clients:
            client.join(timeout=0.5)
        with self._lock:
            self._clients.clear()
            self._pending.clear()
        self._port = 0

    # ---------------------------------------------------------------- accept

    def _accept_loop(self) -> None:
        while not self.stopping.is_set():
            listener = self._listener
            if listener is None:
                return
            try:
                sock, address = listener.accept()
            except TimeoutError:
                continue
            except OSError as exc:
                # Windows surfaces aborted pending connections here
                # (ConnectionResetError / WSAECONNRESET, live 2026-10-16): a
                # stray client reset must never kill the accept loop - the
                # bridge would stay bound but silently stop accepting.
                if self.stopping.is_set() or self._listener is None:
                    return
                logger.debug("bridge: accept() hiccup (%s) - continuing", exc)
                time.sleep(0.05)
                continue
            try:
                self._handshake(sock)
            except (OSError, ProtocolError) as exc:
                logger.debug("bridge: rejected connection from %s (%s)", address, exc)
                try:
                    sock.close()
                except OSError:
                    pass
                continue
            with self._lock:
                if len(self._clients) >= MAX_CLIENTS:
                    logger.warning("bridge: too many clients — dropping %s", address)
                    sock.close()
                    continue
                client = _ClientConnection(self, sock, address)
                self._clients.append(client)
            client.start()
            logger.debug("bridge: connection accepted from %s (client %s)", address, client.id)

    @staticmethod
    def _handshake(sock: socket.socket) -> None:
        """Read the HTTP upgrade request, enforce the origin, answer 101."""
        sock.settimeout(5.0)
        head = b""
        while b"\r\n\r\n" not in head:
            if len(head) > 8192:
                raise ProtocolError("handshake too large")
            chunk = sock.recv(4096)
            if not chunk:
                raise ProtocolError("closed during handshake")
            head += chunk
        request = head.split(b"\r\n\r\n", 1)[0]
        decoded = request.decode("latin-1")
        origin = ""
        for line in decoded.split("\r\n")[1:]:
            name, _, value = line.partition(":")
            if name.strip().lower() == "origin":
                origin = value.strip()
        if not origin.startswith(("chrome-extension://", "moz-extension://")):
            raise ProtocolError(f"origin not allowed: {origin or '(none)'}")
        _key, response = handshake_response(request)
        sock.sendall(response)

    def _forget_client(self, client: _ClientConnection) -> None:
        with self._lock:
            if client in self._clients:
                self._clients.remove(client)
        if client.registered:
            logger.info("bridge: browser extension disconnected (client %s)", client.id)

    # --------------------------------------------------------------- messages

    def _handle_message(self, client: _ClientConnection, message: dict[str, Any]) -> None:
        kind = str(message.get("type", ""))
        if kind == "hello":
            client.registered = True
            client.info = message
            platforms = message.get("platforms")
            if isinstance(platforms, dict):
                self._platform_toggles = dict(platforms)
            logger.info(
                "bridge: extension connected (client %s, v%s)",
                client.id,
                message.get("ext_version", "?"),
            )
        elif kind == "event":
            event = message.get("event")
            if isinstance(event, dict):
                self._handle_event(event)
        elif kind == "result":
            command_id = str(message.get("id", ""))
            with self._lock:
                pending = self._pending.pop(command_id, None)
            if pending is not None:
                pending.box["result"] = {
                    "ok": bool(message.get("ok")),
                    "data": message.get("data") if isinstance(message.get("data"), dict) else {},
                    "error": message.get("error"),
                }
                pending.event.set()

    def _handle_event(self, raw: dict[str, Any]) -> None:
        try:
            record = normalize_event(raw, now=self._clock())
        except ValueError as exc:
            logger.debug("bridge: ignored malformed event (%s)", exc)
            return
        self.store.append(record)
        self._last_event_ms = int(self._clock() * 1000.0)
        self._event_count += 1

        platform = str(record.get("platform", "web"))
        kind = record.get("kind")
        now = self._clock()

        if kind == "unread" and isinstance(record.get("count"), int):
            previous = self._unread.get(platform, {})
            previous_count = previous.get("count", 0)
            self._unread[platform] = {
                "count": record["count"],
                "at": record["ts"],
                "sender": record.get("sender", previous.get("sender", "")),
                "preview": record.get("preview", previous.get("preview", "")),
            }
            if record["count"] > previous_count and self._announcements_enabled():
                last_generic = self._last_announce.get(f"{platform}:unread", 0.0)
                if now - last_generic >= _UNREAD_ANNOUNCE_EVERY:
                    label = _label(platform)
                    text = (
                        f"New activity on {label} — {record['count']} unread."
                        if record["count"] > 1
                        else f"Something new on {label}."
                    )
                    self._pending_unread[platform] = {
                        "text": text,
                        "platform": platform,
                        "kind": "unread",
                        "ts": record.get("ts", int(now * 1000.0)),
                        "sender": "",
                        "preview": "",
                        "_at": now,
                    }
        elif kind == "message":
            sender = str(record.get("sender", "")).strip()
            self._unread.setdefault(platform, {"count": 0, "at": record["ts"]})
            self._unread[platform]["sender"] = sender or self._unread[platform].get("sender", "")
            self._unread[platform]["preview"] = str(record.get("preview", ""))
            # The specific note supersedes a still-pending generic one.
            self._pending_unread.pop(platform, None)
            label = _label(platform)
            text = f"New message on {label} from {sender}." if sender else f"New message on {label}."
            self._queue_message_announcement(platform, text, record)

    def _announcements_enabled(self) -> bool:
        return bool(getattr(self.settings.bridge, "announce_messages", False))

    def _queue_message_announcement(self, platform: str, text: str, record: dict[str, Any]) -> None:
        if not self._announcements_enabled():
            return
        now = self._clock()
        key = f"{platform}:message"
        if now - self._last_announce.get(key, 0.0) < _MESSAGE_ANNOUNCE_EVERY:
            return
        self._last_announce[key] = now
        self._announcements.append(
            {
                "text": text,
                "platform": platform,
                "kind": "message",
                "ts": record.get("ts", int(now * 1000.0)),
                "sender": record.get("sender", ""),
                "preview": record.get("preview", ""),
            }
        )

    def drain_announcements(self) -> list[dict[str, Any]]:
        """Hand the queued notes to the caller (the GUI): pending generic unread
        notes first (after their grace period), then specific message notes."""
        now = self._clock()
        ready: list[dict[str, Any]] = []
        with self._lock:
            for platform, pending in list(self._pending_unread.items()):
                if now - pending.get("_at", now) >= _PENDING_UNREAD_GRACE_SECONDS:
                    note = dict(pending)
                    note.pop("_at", None)
                    ready.append(note)
                    self._last_announce[f"{platform}:unread"] = now
                    del self._pending_unread[platform]
            notes = ready + list(self._announcements)
            self._announcements.clear()
        return notes

    # --------------------------------------------------------------- commands

    def _pick_client(self) -> _ClientConnection | None:
        with self._lock:
            for client in self._clients:
                if client.registered and not client.closed.is_set():
                    return client
        return None

    def send_command(self, name: str, args: dict[str, Any] | None = None, *, timeout: float = 10.0) -> dict[str, Any] | None:
        """Relay one command to the extension.

        Returns ``None`` when no extension is connected (caller narrates that
        honestly); otherwise ``{"ok": bool, "data": dict, "error": str|None}``,
        with ``error="timeout"`` when the extension did not answer in time.
        """
        client = self._pick_client()
        if client is None:
            return None
        command_id = uuid.uuid4().hex
        pending = _Pending()
        with self._lock:
            self._pending[command_id] = pending
        try:
            client.send_json({"v": 1, "type": "command", "id": command_id, "name": name, "args": args or {}})
        except OSError:
            with self._lock:
                self._pending.pop(command_id, None)
            return None
        if not pending.event.wait(timeout):
            with self._lock:
                self._pending.pop(command_id, None)
            return {"ok": False, "data": {}, "error": "timeout"}
        return pending.box.get("result") or {"ok": False, "data": {}, "error": "no result"}

    # ---------------------------------------------------------------- reports

    def unread_report(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {platform: dict(values) for platform, values in self._unread.items()}

    def status(self) -> dict[str, Any]:
        with self._lock:
            clients = len(self._clients)
            registered = sum(1 for client in self._clients if client.registered)
        return {
            "running": self.running,
            "port": self._port,
            "connected": self.connected,
            "clients": clients,
            "registered_clients": registered,
            "events_seen": self._event_count,
            "last_event_ms": self._last_event_ms,
            "unread": self.unread_report(),
            "platforms": dict(self._platform_toggles),
        }
