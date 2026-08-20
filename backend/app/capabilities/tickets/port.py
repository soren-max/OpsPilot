from typing import Protocol

from app.capabilities.tickets.models import TicketQuery, TicketRecord


class TicketsCapability(Protocol):
    async def search(self, query: TicketQuery) -> tuple[TicketRecord, ...]: ...
