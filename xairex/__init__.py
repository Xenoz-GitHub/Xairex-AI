"""Xairex — a fully offline, CPU-only personal voice assistant.

This package contains the runtime application. Nothing under ``xairex/`` may
perform network access other than loopback calls to the local Ollama server
(see notes/02-ARCHITECTURE.md, section "Offline guardrails").
"""

__version__ = "0.1.0"
