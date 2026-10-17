"""Loopback-only Ollama client (spec section 5).

Design rules:

* The URL must be loopback; anything else is rejected at construction time.
* The heavy ``ollama`` package is imported lazily so unit tests (and the rest
  of the app) do not require a running server or the package to be installed.
* Failures are mapped to ``BrainError`` subclasses with user-actionable text.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from xairex.security.policy import is_loopback_url

logger = logging.getLogger("xairex.brain")


class BrainError(RuntimeError):
    """Base class for local-brain failures with user-facing messages."""


class BrainUnavailableError(BrainError):
    """Ollama is not reachable at the configured loopback address."""


class BrainModelMissingError(BrainError):
    """The configured local model is not present in Ollama."""


class BrainTimeoutError(BrainError):
    """The local model did not respond within the configured timeout."""


class BrainCancelledError(BrainError):
    """The user stopped the request while the model was still generating."""


@dataclass(frozen=True)
class ToolCallRequest:
    """A tool call requested by the model (validated later by the tool registry)."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrainReply:
    """One model reply: final text and/or tool-call requests."""

    content: str
    tool_calls: tuple[ToolCallRequest, ...] = ()
    thinking: str | None = None


@dataclass(frozen=True)
class BrainHealth:
    """Result of a local health probe against Ollama."""

    reachable: bool
    model_present: bool
    detail: str


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Read a field from dict-like or attribute-style objects.

    The Ollama client returns pydantic-style objects, but tests and future
    client versions may hand us plain dicts.
    """
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def list_local_models(base_url: str, *, timeout_seconds: float = 5.0, client: Any | None = None) -> list[str]:
    """Names of the models installed in the local Ollama server (G4 picker).

    Loopback-only, like everything else in this module. Raises
    :class:`BrainError` when the server cannot be reached or queried; callers
    that merely populate a picker catch it and keep the configured name.
    """
    if not is_loopback_url(base_url):
        raise BrainError(f"Refusing non-loopback Ollama URL {base_url!r}: Xairex only talks to the local machine.")
    if client is None:
        try:
            from ollama import Client
        except ImportError as exc:
            raise BrainError("The 'ollama' Python package is not installed. Run scripts\\install.ps1.") from exc
        client = Client(host=base_url.rstrip("/"), timeout=timeout_seconds)
    try:
        response = client.list()
    except Exception as exc:
        raise BrainError(f"Could not list local Ollama models: {exc}") from exc
    names: list[str] = []
    for entry in _get(response, "models", None) or []:
        name = _get(entry, "model", None) or _get(entry, "name", None)
        if name:
            names.append(str(name))
    return sorted(dict.fromkeys(names))


class OllamaBrain:
    """Thin wrapper around ``ollama.Client`` pinned to loopback."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float = 120.0,
        num_ctx: int = 4096,
        temperature: float = 0.6,
        keep_alive: str | int = "5m",
        think: bool | None = True,
        client: Any | None = None,
    ) -> None:
        if not is_loopback_url(base_url):
            raise ValueError(f"Refusing non-loopback Ollama URL {base_url!r}: Xairex only talks to the local machine.")
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._options = {"num_ctx": num_ctx, "temperature": temperature}
        self._keep_alive = keep_alive
        self._think = None if think is None else bool(think)
        self._client = client

    @classmethod
    def from_settings(cls, settings: Any, client: Any | None = None) -> OllamaBrain:
        """Build from :class:`xairex.config.Settings`."""
        brain = settings.brain
        return cls(
            base_url=brain.base_url,
            model=brain.model,
            timeout_seconds=brain.timeout_seconds,
            num_ctx=brain.num_ctx,
            temperature=brain.temperature,
            keep_alive=brain.keep_alive,
            think=brain.think,
            client=client,
        )

    # ------------------------------------------------------------------ client

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                from ollama import Client
            except ImportError as exc:
                raise BrainError("The 'ollama' Python package is not installed. Run scripts\\install.ps1.") from exc
            logger.debug("Creating Ollama client for %s", self._base_url)
            self._client = Client(host=self._base_url, timeout=self._timeout_seconds)
        return self._client

    def close(self) -> None:
        """Best-effort cleanup of the underlying HTTP client."""
        client, self._client = self._client, None
        if client is None:
            return
        close = getattr(client, "close", None)
        if callable(close):
            try:
                close()
            except Exception:  # pragma: no cover - defensive
                logger.debug("Ignoring error while closing Ollama client", exc_info=True)

    # ------------------------------------------------------------------ health

    def health(self) -> BrainHealth:
        """Probe the local server and the configured model. Never raises."""
        try:
            client = self._ensure_client()
            listing = client.list()
        except BrainError as exc:
            return BrainHealth(False, False, str(exc))
        except Exception as exc:  # noqa: BLE001 - health checks must never raise
            return BrainHealth(
                False,
                False,
                f"Ollama is not reachable at {self._base_url} "
                f"({type(exc).__name__}: {exc}). Start it with 'ollama serve'.",
            )

        names: list[str] = []
        for entry in _get(listing, "models", []) or []:
            name = _get(entry, "model") or _get(entry, "name") or ""
            if name:
                names.append(str(name))

        model_present = any(name.split(":")[0] == self._model for name in names)
        if model_present:
            detail = f"model '{self._model}' found at {self._base_url}"
        else:
            available = ", ".join(sorted(names)) or "none"
            detail = (
                f"model '{self._model}' not found at {self._base_url} "
                f"(available: {available}). Run scripts\\prepare_models.ps1."
            )
        return BrainHealth(True, model_present, detail)

    # -------------------------------------------------------------------- chat

    def chat(
        self,
        messages: Sequence[dict],
        tools: Sequence[dict] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> BrainReply:
        """One chat round against the local model. Raises :class:`BrainError`.

        The request runs on a worker thread behind a wall-clock watchdog.
        ``timeout_seconds`` stops runaway *generation* (a very long thinking
        trace streams token-by-token, so an HTTP read timeout never fires —
        observed 2026-10-16: one answer took 21 minutes), and ``cancel_event``
        (the 'stop' command) aborts even sooner by closing the HTTP stream.
        """
        client = self._ensure_client()
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": list(messages),
            "options": dict(self._options),
            "keep_alive": self._keep_alive,
        }
        if self._think is not None:  # None = omit the flag (non-thinking models)
            kwargs["think"] = self._think
        if tools:
            kwargs["tools"] = list(tools)

        result: dict[str, Any] = {}

        def _call() -> None:
            try:
                result["response"] = client.chat(**kwargs)
            except Exception as exc:  # noqa: BLE001 - mapped and re-raised on the caller's thread
                result["error"] = exc

        worker = threading.Thread(target=_call, name="xairex-brain-call", daemon=True)
        worker.start()
        deadline = time.monotonic() + self._timeout_seconds
        while worker.is_alive():
            if cancel_event is not None and cancel_event.is_set():
                self.close()  # abort the in-flight HTTP stream
                raise BrainCancelledError("Request stopped.")
            if time.monotonic() > deadline:
                self.close()
                raise BrainTimeoutError(
                    f"The local model kept generating for over {self._timeout_seconds:.0f}s and was stopped "
                    "(usually a runaway thinking trace). Try a shorter question, or type 'stop' sooner."
                )
            worker.join(timeout=0.1)

        if "error" in result:
            raise self._map_error(result["error"]) from result["error"]
        response = result["response"]

        message = _get(response, "message")
        content = str(_get(message, "content", "") or "")
        # Safety net: with think=false (not recommended) Qwen3 emits its reasoning
        # trace inline as '...reasoning...</think>answer'. Reasoning must never
        # reach the user's ears, so keep only what follows the last marker.
        if "</think>" in content:
            content = content.rsplit("</think>", 1)[-1].strip()
        thinking_raw = _get(message, "thinking")
        thinking = str(thinking_raw) if thinking_raw else None

        calls: list[ToolCallRequest] = []
        for call in _get(message, "tool_calls", []) or []:
            function = _get(call, "function")
            name = str(_get(function, "name", "") or "")
            arguments = _get(function, "arguments") or {}
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    logger.warning("Model returned non-JSON tool arguments for %r; ignoring them.", name)
                    arguments = {}
            if not isinstance(arguments, dict):
                arguments = {}
            if name:
                calls.append(ToolCallRequest(name=name, arguments=arguments))

        logger.debug("brain reply: content=%d chars, tool_calls=%d", len(content), len(calls))
        return BrainReply(content=content, tool_calls=tuple(calls), thinking=thinking)

    # ------------------------------------------------------------ error mapping

    def _map_error(self, exc: Exception) -> BrainError:
        """Translate client/HTTP exceptions into actionable BrainError text."""
        name = type(exc).__name__
        text = str(exc)
        status = getattr(exc, "status_code", None)

        if status == 404 or "not found" in text.lower():
            return BrainModelMissingError(
                f"Local model '{self._model}' is missing. "
                "Run scripts\\prepare_models.ps1 (it pulls the models and creates the local aliases)."
            )
        if "connect" in name.lower() or isinstance(exc, ConnectionError):
            return BrainUnavailableError(
                f"Ollama is not running at {self._base_url}. Start it with 'ollama serve' and try again."
            )
        if "timeout" in name.lower() or isinstance(exc, TimeoutError):
            return BrainTimeoutError(
                f"The local model did not answer within {self._timeout_seconds:.0f}s. "
                "It may still be loading; try again, or raise brain.timeout_seconds."
            )
        if status is not None:
            return BrainError(f"Ollama returned an error (HTTP {status}): {text}")
        return BrainError(f"Local brain error ({name}): {text}")
