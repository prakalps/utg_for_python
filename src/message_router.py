"""Non-mathematical complex example module for the AI test runner.

Contains:
- parsing + validation
- branching logic
- dataclasses
- a small stateful router class
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Mapping


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class Message:
    sender: str
    recipient: str
    body: str
    severity: Severity = Severity.INFO
    created_at: datetime | None = None

    def normalized_recipient(self) -> str:
        return self.recipient.strip().lower()


def parse_message(raw: str) -> Message:
    """Parse format: 'from=<sender>;to=<recipient>;severity=<level>;body=<text>'."""
    if not raw or not raw.strip():
        raise ValueError("raw message must be non-empty")

    parts = [chunk.strip() for chunk in raw.split(";") if chunk.strip()]
    data: dict[str, str] = {}
    for part in parts:
        if "=" not in part:
            raise ValueError("invalid message part")
        key, value = part.split("=", 1)
        data[key.strip().lower()] = value.strip()

    sender = data.get("from")
    recipient = data.get("to")
    body = data.get("body")
    severity_text = data.get("severity", "info").strip().lower()

    if not sender:
        raise ValueError("missing sender")
    if not recipient:
        raise ValueError("missing recipient")
    if body is None:
        raise ValueError("missing body")

    if severity_text not in {"info", "warning", "error"}:
        raise ValueError("invalid severity")

    return Message(
        sender=sender,
        recipient=recipient,
        body=body,
        severity=Severity(severity_text),
        created_at=datetime.utcnow(),
    )


class MessageRouter:
    def __init__(self, routes: Mapping[str, str] | None = None) -> None:
        self._routes = {k.strip().lower(): v for k, v in (routes or {}).items()}
        self._sent_count = 0

    def route_for(self, recipient: str) -> str:
        key = recipient.strip().lower()
        if not key:
            raise ValueError("recipient must be non-empty")
        return self._routes.get(key, "default")

    def send(self, message: Message) -> str:
        self._sent_count += 1
        target = self.route_for(message.recipient)
        if message.severity == Severity.ERROR:
            return f"[{target}] ALERT: {message.body}"
        if message.severity == Severity.WARNING:
            return f"[{target}] WARN: {message.body}"
        return f"[{target}] OK: {message.body}"

    def sent_count(self) -> int:
        return self._sent_count
