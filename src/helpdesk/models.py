from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Status(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


@dataclass(frozen=True)
class Ticket:
    id: str
    requester: str
    title: str
    description: str
    priority: Priority = Priority.MEDIUM
    status: Status = Status.OPEN
    tags: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class Comment:
    ticket_id: str
    author: str
    body: str
    created_at: datetime = field(default_factory=datetime.utcnow)
