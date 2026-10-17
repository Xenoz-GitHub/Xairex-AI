"""Typed tool registry: validation, hard timeouts and audit (spec section 6, D5).

Every tool call — whether the no-LLM router or the language model requested it —
goes through :meth:`ToolRegistry.execute`. Arguments are validated against a
small JSON-schema subset, handlers run under a wall-clock timeout, and every
outcome is audited. Model output never reaches the operating system without
passing through here (golden rule 5).
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("xairex.tools")


@dataclass(frozen=True)
class ToolResult:
    """Outcome of one tool execution.

    ``message`` is written to be safe to speak; ``data`` may carry extra
    structured info (e.g. ``{"open": "ms-settings:..."}`` fallbacks).
    """

    ok: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolSpec:
    """One registered tool: schema for the model, handler for the machine."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[dict[str, Any]], ToolResult]
    timeout_seconds: float = 5.0


#: Called with (tool name, arguments, result, duration seconds) after every run.
AuditHook = Callable[[str, dict[str, Any], ToolResult, float], None]


# ------------------------------------------------------------------ validation


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    return False


def validate_arguments(schema: dict[str, Any], arguments: Any) -> list[str]:
    """Validate *arguments* against a small JSON-schema subset.

    Supported: ``type`` (object/string/integer/number/boolean), ``properties``,
    ``required``, ``enum``, ``minimum``, ``maximum``. Returns human-readable
    problems (empty list = valid). Unknown parameters are rejected loudly so
    typos cannot silently do nothing.
    """
    if not isinstance(arguments, dict):
        return ["arguments must be an object"]
    problems: list[str] = []
    properties = schema.get("properties", {})
    for name in schema.get("required", []):
        if name not in arguments:
            problems.append(f"missing required parameter {name!r}")
    for name, value in arguments.items():
        rule = properties.get(name)
        if rule is None:
            problems.append(f"unexpected parameter {name!r}")
            continue
        expected = rule.get("type")
        if expected and not _type_ok(value, expected):
            problems.append(f"parameter {name!r} must be {expected}")
            continue
        if "enum" in rule and value not in rule["enum"]:
            allowed = ", ".join(map(str, rule["enum"]))
            problems.append(f"parameter {name!r} must be one of: {allowed}")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in rule and value < rule["minimum"]:
                problems.append(f"parameter {name!r} must be >= {rule['minimum']}")
            if "maximum" in rule and value > rule["maximum"]:
                problems.append(f"parameter {name!r} must be <= {rule['maximum']}")
    return problems


# ------------------------------------------------------------------- registry


class ToolRegistry:
    """Holds the allowed tools; the single execution chokepoint."""

    def __init__(self, *, audit: AuditHook | None = None) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._disabled: set[str] = set()
        self._audit = audit

    # ------------------------------------------------------------ registration

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"tool {spec.name!r} is already registered")
        self._tools[spec.name] = spec

    def disable(self, *names: str) -> None:
        """Switch tools off (settings toggles). Unknown names are ignored."""
        self._disabled.update(names)

    # ------------------------------------------------------------------ queries

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def is_enabled(self, name: str) -> bool:
        return name in self._tools and name not in self._disabled

    def specs(self) -> list[ToolSpec]:
        return [spec for name, spec in sorted(self._tools.items()) if name not in self._disabled]

    def ollama_tools(self) -> list[dict[str, Any]]:
        """The enabled tools in Ollama's ``tools=`` request format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
                },
            }
            for spec in self.specs()
        ]

    # ---------------------------------------------------------------- execution

    def execute(self, name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
        """Validate, run under a hard timeout and audit one tool call."""
        arguments = dict(arguments or {})

        spec = self._tools.get(name)
        if spec is None:
            return self._finish(name, arguments, ToolResult(False, f"Unknown tool {name!r}."), 0.0)
        if name in self._disabled:
            return self._finish(name, arguments, ToolResult(False, f"The {name} feature is disabled in settings."), 0.0)

        problems = validate_arguments(spec.parameters, arguments)
        if problems:
            return self._finish(name, arguments, ToolResult(False, "Invalid arguments: " + "; ".join(problems)), 0.0)

        box: dict[str, Any] = {}

        def _run() -> None:
            try:
                box["result"] = spec.handler(dict(arguments))
            except Exception as exc:  # noqa: BLE001 - reported, never fatal
                box["error"] = exc

        started = time.monotonic()
        worker = threading.Thread(target=_run, name=f"xairex-tool-{name}", daemon=True)
        worker.start()
        worker.join(spec.timeout_seconds)
        duration = time.monotonic() - started

        if worker.is_alive():
            result = ToolResult(False, f"The {name} action timed out after {spec.timeout_seconds:.0f}s.")
        elif "error" in box:
            exc = box["error"]
            logger.error("tool %s crashed: %s", name, exc, exc_info=exc)
            result = ToolResult(False, f"The {name} action failed unexpectedly ({type(exc).__name__}). See the log.")
        else:
            value = box.get("result")
            if isinstance(value, ToolResult):
                result = value
            else:  # defensive: handlers must return ToolResult
                result = ToolResult(False, f"The {name} action returned no result.")

        return self._finish(name, arguments, result, duration)

    def _finish(self, name: str, arguments: dict[str, Any], result: ToolResult, duration: float) -> ToolResult:
        if self._audit is not None:
            try:
                self._audit(name, arguments, result, duration)
            except Exception:  # pragma: no cover - auditing must never break a tool call
                logger.exception("tool audit hook failed for %s", name)
        return result
