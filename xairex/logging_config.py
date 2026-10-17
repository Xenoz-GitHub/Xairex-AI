"""Logging setup with privacy-preserving defaults (spec section 14).

Console output is always on — default level WARNING so the styled CLI stays
clean; raise ``logging.console_level`` to INFO/DEBUG when troubleshooting.
A rotating local file is optional and keeps the full configured detail.
Private content (transcripts, answers, tool arguments) is only written to the
log when the user explicitly enables ``logging.debug_log_private``.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from xairex.config import Settings

#: Third-party loggers that are useful at WARNING and noisy below it.
_NOISY_LOGGERS = (
    "faster_whisper",
    "httpx",
    "httpcore",
    "urllib3",
    "onnxruntime",
    "openwakeword",
    "numexpr",
)

_private_logging = False


def setup_logging(settings: Settings) -> logging.Logger:
    """Configure and return the ``xairex`` logger. Safe to call more than once."""
    global _private_logging
    _private_logging = bool(settings.logging.debug_log_private)

    logger = logging.getLogger("xairex")
    logger.setLevel(settings.logging.level)
    logger.propagate = False

    # Allow repeated setup (tests, restarts) without duplicate handlers.
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S")

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(settings.logging.console_level)
    logger.addHandler(console)

    if settings.logging.file_enabled:
        log_path = settings.resolve_path(settings.logging.file_path)
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except OSError as exc:  # pragma: no cover - depends on local filesystem
            logger.warning("Could not open log file %s (%s); continuing with console only.", log_path, exc)

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    return logger


def private_logging_enabled() -> bool:
    """True when the user explicitly allowed private content in the log."""
    return _private_logging


def log_text(logger: logging.Logger, label: str, text: str, level: int = logging.DEBUG) -> None:
    """Log *text* only when private logging is enabled; otherwise log its length."""
    if _private_logging:
        logger.log(level, "%s: %s", label, text)
    else:
        logger.log(level, "%s: <%d chars>", label, len(text))
