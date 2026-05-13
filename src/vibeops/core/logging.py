from __future__ import annotations

import logging
import re
import sys

_REDACTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"), "sk-***REDACTED***"),
    (
        re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----[\s\S]+?-----END [A-Z ]+PRIVATE KEY-----"),
        "***PEM-REDACTED***",
    ),
    (re.compile(r'"private_key":\s*"[^"]+"'), '"private_key": "***REDACTED***"'),
    (re.compile(r'"client_email":\s*"[^"]+"'), '"client_email": "***REDACTED***"'),
]


class RedactingFormatter(logging.Formatter):
    """Logging formatter that strips credentials from every log message."""

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        for pattern, replacement in _REDACTION_PATTERNS:
            message = pattern.sub(replacement, message)
        return message


def configure_logging(level: str = "INFO") -> None:
    """Attach a redacting stdout handler to the root logger."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
