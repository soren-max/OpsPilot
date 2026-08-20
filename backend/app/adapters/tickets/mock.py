from app.capabilities.tickets import TicketQuery, TicketRecord


class MockTicketAdapter:
    """Deterministic fixture-backed ticket capability; no SaaS binding in M3A."""

    def __init__(self, records: tuple[TicketRecord, ...] = ()) -> None:
        self._records = records

    async def search(self, query: TicketQuery) -> tuple[TicketRecord, ...]:
        matches = [
            item
            for item in self._records
            if item.service == query.service
            and item.environment == query.environment
            and (query.status is None or item.status == query.status)
            and query.start <= item.created_at <= query.end
            and all(
                keyword.lower() in f"{item.title} {item.summary} {item.resolution or ''}".lower()
                for keyword in query.keywords
            )
        ]
        matches.sort(key=lambda item: (item.created_at, item.id), reverse=True)
        return tuple(matches[: query.limit])
