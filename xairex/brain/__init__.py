"""Local language-model brain: Ollama client, conversation, prompts."""

from xairex.brain.conversation import Conversation
from xairex.brain.ollama_client import (
    BrainError,
    BrainModelMissingError,
    BrainReply,
    BrainTimeoutError,
    BrainUnavailableError,
    OllamaBrain,
    ToolCallRequest,
)
from xairex.brain.prompts import XAIREX_SYSTEM_PROMPT, build_system_prompt

__all__ = [
    "XAIREX_SYSTEM_PROMPT",
    "BrainError",
    "BrainModelMissingError",
    "BrainReply",
    "BrainTimeoutError",
    "BrainUnavailableError",
    "Conversation",
    "OllamaBrain",
    "ToolCallRequest",
    "build_system_prompt",
]
