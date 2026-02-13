from __future__ import annotations

from helpdesk.api import handle_request
from helpdesk.service import TicketService


def run_demo() -> str:
    service = TicketService()
    ticket_id = handle_request(
        service,
        {
            "action": "create",
            "id": "HD-000001",
            "requester": "user@example.com",
            "title": "Payment outage",
            "description": "Checkout is down for all users",
            "priority": "high",
            "tags": ["payments", "prod"],
        },
    )
    handle_request(
        service,
        {
            "action": "comment",
            "id": ticket_id,
            "author": "agent@example.com",
            "body": "Investigating now",
        },
    )
    return ticket_id
