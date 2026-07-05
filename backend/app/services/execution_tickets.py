from datetime import datetime, timezone

from app.models.service import ExecutionTicket


class TicketStateError(RuntimeError):
    pass


def use_execution_ticket(ticket: ExecutionTicket) -> None:
    if ticket.status != "issued":
        raise TicketStateError(f"Ticket is not usable: {ticket.status}")
    ticket.status = "used"
    ticket.used_at = datetime.now(timezone.utc)
