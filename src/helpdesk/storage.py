from __future__ import annotations

from dataclasses import replace
from typing import Dict, Iterable, Sequence

from helpdesk.models import Comment, Ticket
from helpdesk.utils import validate_ticket_id


class InMemoryTicketStore:
    def __init__(self) -> None:
        self._tickets: Dict[str, Ticket] = {}
        self._comments: Dict[str, list[Comment]] = {}

    def add_ticket(self, ticket: Ticket) -> None:
        validate_ticket_id(ticket.id)
        if ticket.id in self._tickets:
            raise ValueError("ticket already exists")
        self._tickets[ticket.id] = ticket
        self._comments.setdefault(ticket.id, [])

    def get_ticket(self, ticket_id: str) -> Ticket:
        validate_ticket_id(ticket_id)
        try:
            return self._tickets[ticket_id]
        except KeyError as exc:
            raise ValueError("ticket not found") from exc

    def list_tickets(self) -> Sequence[Ticket]:
        return tuple(self._tickets.values())

    def update_ticket(self, ticket_id: str, **fields: object) -> Ticket:
        ticket = self.get_ticket(ticket_id)
        updated = replace(ticket, **fields)
        self._tickets[ticket_id] = updated
        return updated

    def add_comment(self, comment: Comment) -> None:
        validate_ticket_id(comment.ticket_id)
        if comment.ticket_id not in self._tickets:
            raise ValueError("ticket not found")
        self._comments.setdefault(comment.ticket_id, []).append(comment)

    def list_comments(self, ticket_id: str) -> Iterable[Comment]:
        validate_ticket_id(ticket_id)
        return tuple(self._comments.get(ticket_id, []))
