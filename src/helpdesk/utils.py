from __future__ import annotations

import re


_TICKET_ID_RE = re.compile(r"^HD-\d{6}$")


def validate_ticket_id(ticket_id: str) -> None:
    if not _TICKET_ID_RE.match(ticket_id.strip()):
        raise ValueError("invalid ticket id")


def normalize_email(email: str) -> str:
    email = email.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ValueError("invalid email")
    return email


def summarize_text(text: str, max_len: int = 80) -> str:
    text = " ".join(text.strip().split())
    if max_len <= 0:
        raise ValueError("max_len must be positive")
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"
