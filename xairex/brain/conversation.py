"""Conversation context management (spec sections 5 and 8; G14 persistent memory).

Keeps the system prompt plus a bounded number of recent messages. History
growth is limited by message count; Ollama's ``num_ctx`` remains the hard token
bound. A trim may split an old tool round-trip — trimming only happens between
completed requests and old tool messages are harmless to drop first.

G14 adds persistent memory: conversation history can be saved/loaded from
SQLite so Xairex remembers previous conversations across sessions.
"""

from __future__ import annotations

from typing import Any

from xairex.brain.prompts import XAIREX_SYSTEM_PROMPT


class Conversation:
    """Builds Ollama message lists and remembers recent turns (with optional persistence)."""

    def __init__(
        self,
        system_prompt: str = XAIREX_SYSTEM_PROMPT,
        history_limit: int = 12,
        db: Any = None,
        persist: bool = False,
    ) -> None:
        self._system_prompt = system_prompt
        self._history_limit = max(0, int(history_limit))
        self._messages: list[dict[str, Any]] = []
        self._db = db
        self._persist = persist and db is not None

        # Load history from database if persistence is enabled
        if self._persist:
            self._load_from_db()

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    @property
    def messages(self) -> list[dict[str, Any]]:
        """A copy of the stored (already trimmed) history."""
        return list(self._messages)

    def build(self, user_text: str) -> list[dict[str, Any]]:
        """System prompt + trimmed history + the new user message (not stored)."""
        messages: list[dict[str, Any]] = [{"role": "system", "content": self._system_prompt}]
        messages.extend(self._messages)
        messages.append({"role": "user", "content": user_text})
        return messages

    def commit(self, user_text: str, assistant_text: str) -> None:
        """Store a completed exchange and trim history to the configured limit."""
        self._append({"role": "user", "content": user_text})
        self._append({"role": "assistant", "content": assistant_text})

    def commit_assistant(self, assistant_message: dict[str, Any]) -> None:
        """Append a raw assistant message (used by the tool-call loop)."""
        self._append(dict(assistant_message))

    def commit_tool_result(self, tool_name: str, content: str) -> None:
        """Append a tool result message for the model's next round."""
        self._append({"role": "tool", "tool_name": tool_name, "content": content})

    def reset(self) -> None:
        """Clear conversation history (user action or end of session)."""
        self._messages.clear()
        if self._persist:
            self._db.clear_conversation_history()

    def clear_history(self) -> None:
        """Alias for reset() - clear conversation history."""
        self.reset()

    def _append(self, message: dict[str, Any]) -> None:
        self._messages.append(message)
        
        # Save to database if persistence is enabled
        if self._persist and "role" in message and "content" in message:
            self._db.save_conversation_turn(message["role"], message["content"])
        
        # Trim to history limit
        if self._history_limit and len(self._messages) > self._history_limit:
            del self._messages[: len(self._messages) - self._history_limit]

    def _load_from_db(self) -> None:
        """Load conversation history from database."""
        if not self._db:
            return
        try:
            history = self._db.load_conversation_history(self._history_limit)
            self._messages = history
        except Exception:
            # If loading fails, start fresh
            self._messages = []
