from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Sequence

from helpdesk.models import Comment, Priority, Status, Ticket
from helpdesk.storage import InMemoryTicketStore
from helpdesk.utils import normalize_email, summarize_text


class TicketService:
    def __init__(self, store: InMemoryTicketStore | None = None) -> None:
        self._store = store or InMemoryTicketStore()

    def create_ticket(
        self,
        ticket_id: str,
        requester_email: str,
        title: str,
        description: str,
        priority: Priority = Priority.MEDIUM,
        tags: Sequence[str] = (),
    ) -> Ticket:
        requester = normalize_email(requester_email)
        title = summarize_text(title, max_len=60)
        description = description.strip()
        if not description:
            raise ValueError("description must be non-empty")

        ticket = Ticket(
            id=ticket_id.strip(),
            requester=requester,
            title=title,
            description=description,
            priority=priority,
            status=Status.OPEN,
            tags=tuple(t.strip().lower() for t in tags if t.strip()),
        )
        self._store.add_ticket(ticket)
        return ticket

    def add_comment(self, ticket_id: str, author_email: str, body: str) -> Comment:
        author = normalize_email(author_email)
        body = body.strip()
        if not body:
            raise ValueError("comment body must be non-empty")
        comment = Comment(ticket_id=ticket_id.strip(), author=author, body=body)
        self._store.add_comment(comment)
        return comment

    def assign_priority(self, ticket_id: str, priority: Priority) -> Ticket:
        return self._store.update_ticket(ticket_id, priority=priority)

    def transition(self, ticket_id: str, new_status: Status) -> Ticket:
        ticket = self._store.get_ticket(ticket_id)
        allowed = {
            Status.OPEN: {Status.IN_PROGRESS, Status.CLOSED},
            Status.IN_PROGRESS: {Status.RESOLVED, Status.CLOSED},
            Status.RESOLVED: {Status.CLOSED, Status.IN_PROGRESS},
            Status.CLOSED: set(),
        }
        if new_status not in allowed.get(ticket.status, set()):
            raise ValueError("invalid status transition")
        updated = replace(ticket, status=new_status)
        self._store.update_ticket(ticket_id, status=updated.status)
        return updated

    def list_tickets(self) -> Sequence[Ticket]:
        return self._store.list_tickets()

    def list_comments(self, ticket_id: str) -> Iterable[Comment]:
        return self._store.list_comments(ticket_id)
