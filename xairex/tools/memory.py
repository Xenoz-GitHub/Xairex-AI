"""Profile memory and identity tools (G14, owner: "doesn't forget who she is... no amnesia").

Implements persistent identity and memory across sessions:
1. Profile facts ("remember that...") stored in SQLite
2. Identity card injected into every conversation  
3. Conversation history persists (when enabled)

No cloud services, no external memory — everything stays local.
"""

from __future__ import annotations

from xairex.config import Settings
from xairex.memory.database import Database
from xairex.tools.registry import ToolResult, ToolSpec


def remember_tool(settings: Settings, db: Database) -> ToolSpec:
    """Store profile facts (user preferences, name, context)."""

    def handler(args: dict) -> ToolResult:
        key = str(args.get("key", "")).strip()
        value = str(args.get("value", "")).strip()

        if not key:
            return ToolResult(False, "Tell me what to remember (I need a key like 'name' or 'favorite_color').")
        if not value:
            return ToolResult(False, f"Tell me what to remember about '{key}'.")

        # Normalize key
        key = key.lower().replace(" ", "_")

        db.set_profile_fact(key, value)
        return ToolResult(
            True,
            f"Got it — I'll remember that {key} is {value}.",
            data={"action": "remember", "key": key, "value": value},
        )

    return ToolSpec(
        name="remember",
        description=(
            "Store a profile fact about the user (e.g., their name, preferences, context). "
            "Use this when the user says 'remember that...' or tells you personal information to keep."
        ),
        parameters={
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "What to remember (e.g., 'name', 'favorite_color', 'project_name').",
                },
                "value": {
                    "type": "string",
                    "description": "The value to remember.",
                },
            },
            "required": ["key", "value"],
        },
        handler=handler,
        timeout_seconds=5.0,
    )


def recall_tool(settings: Settings, db: Database) -> ToolSpec:
    """Retrieve profile facts."""

    def handler(args: dict) -> ToolResult:
        action = str(args.get("action", "list")).strip().lower()

        if action == "list":
            facts = db.all_profile_facts()
            if not facts:
                return ToolResult(True, "I don't have any profile facts stored yet.")
            lines = [f"- {key}: {value}" for key, value in sorted(facts.items())]
            return ToolResult(
                True,
                f"Here's what I remember:\n{chr(10).join(lines)}",
                data={"action": "list", "facts": facts},
            )

        if action == "get":
            key = str(args.get("key", "")).strip().lower().replace(" ", "_")
            if not key:
                return ToolResult(False, "Tell me what to recall (I need a key).")
            value = db.get_profile_fact(key)
            if value is None:
                return ToolResult(False, f"I don't have anything stored for '{key}'.")
            return ToolResult(
                True,
                f"{key} is {value}",
                data={"action": "get", "key": key, "value": value},
            )

        if action == "forget":
            key = str(args.get("key", "")).strip().lower().replace(" ", "_")
            if not key:
                return ToolResult(False, "Tell me what to forget.")
            deleted = db.delete_profile_fact(key)
            if not deleted:
                return ToolResult(False, f"I don't have anything stored for '{key}'.")
            return ToolResult(
                True,
                f"Okay — I forgot about {key}.",
                data={"action": "forget", "key": key},
            )

        return ToolResult(False, f"I don't know the recall action '{action}'.")

    return ToolSpec(
        name="recall",
        description=(
            "Retrieve stored profile facts. Actions: 'list' shows all facts, "
            "'get' retrieves a specific key, 'forget' deletes a key."
        ),
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "get", "forget"],
                    "description": "What to do.",
                },
                "key": {
                    "type": "string",
                    "description": "Key to get or forget (required for 'get' and 'forget' actions).",
                },
            },
            "required": ["action"],
        },
        handler=handler,
        timeout_seconds=5.0,
    )


def get_identity_facts(db: Database) -> str:
    """Build identity/profile section for system prompt."""
    facts = db.all_profile_facts()
    if not facts:
        return ""

    lines = ["WHAT I KNOW ABOUT YOU:"]
    lines.extend(f"- {key}: {value}" for key, value in sorted(facts.items()))
    return "\n".join(lines)
