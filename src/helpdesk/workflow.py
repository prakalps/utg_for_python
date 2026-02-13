from __future__ import annotations

from helpdesk.models import Priority, Status
from helpdesk.service import TicketService


def auto_triage(service: TicketService, ticket_id: str) -> None:
    ticket = service._store.get_ticket(ticket_id)

    text = f"{ticket.title} {ticket.description}".lower()
    if "outage" in text or "down" in text or "payment" in text:
        service.assign_priority(ticket_id, Priority.HIGH)
    elif "slow" in text or "latency" in text:
        service.assign_priority(ticket_id, Priority.MEDIUM)
    else:
        service.assign_priority(ticket_id, Priority.LOW)

    if ticket.priority == Priority.HIGH:
        service.transition(ticket_id, Status.IN_PROGRESS)
