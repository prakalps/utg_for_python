from __future__ import annotations

from typing import Mapping

from helpdesk.models import Priority, Status
from helpdesk.service import TicketService


def handle_request(service: TicketService, payload: Mapping[str, object]) -> str:
    action = str(payload.get("action", "")).strip().lower()
    if not action:
        raise ValueError("missing action")

    if action == "create":
        ticket = service.create_ticket(
            ticket_id=str(payload.get("id", "")),
            requester_email=str(payload.get("requester", "")),
            title=str(payload.get("title", "")),
            description=str(payload.get("description", "")),
            priority=Priority(str(payload.get("priority", "medium")).lower()),
            tags=tuple(payload.get("tags", []) or ()),
        )
        return ticket.id

    if action == "comment":
        service.add_comment(
            ticket_id=str(payload.get("id", "")),
            author_email=str(payload.get("author", "")),
            body=str(payload.get("body", "")),
        )
        return "ok"

    if action == "transition":
        service.transition(
            ticket_id=str(payload.get("id", "")),
            new_status=Status(str(payload.get("status", "")).lower()),
        )
        return "ok"

    raise ValueError("unknown action")
