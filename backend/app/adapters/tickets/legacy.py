import os
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.adapters.http import JsonHttpClient
from app.capabilities.errors import CapabilityMalformedResponse
from app.capabilities.tickets import TicketQuery, TicketRecord


class LegacyTicketPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=300)
    status: str = Field(min_length=1, max_length=40)
    service: str = Field(min_length=1, max_length=120)
    environment: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=1000)
    resolution: str | None = Field(default=None, max_length=1000)
    created_at: datetime
    resolved_at: datetime | None = None


class LegacyTicketResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tickets: tuple[LegacyTicketPayload, ...] = Field(max_length=100)


class LegacyTicketAdapter:
    """Reference adapter for a bounded synthetic existing-ticket HTTP contract."""

    def __init__(
        self,
        client: JsonHttpClient,
        *,
        tickets_path: str = "/tickets",
        auth_token_env_ref: str | None = None,
    ) -> None:
        self.client = client
        self.tickets_path = tickets_path
        self.auth_token_env_ref = auth_token_env_ref

    async def search(self, query: TicketQuery) -> tuple[TicketRecord, ...]:
        headers: dict[str, str] | None = None
        if self.auth_token_env_ref:
            token = os.environ.get(self.auth_token_env_ref)
            if not token:
                raise RuntimeError("Required legacy ticket credential is unavailable")
            headers = {"Authorization": f"Bearer {token}"}
        payload = await self.client.get_json(
            self.tickets_path,
            params={
                "service": query.service,
                "environment": query.environment,
                "start": query.start.isoformat(),
                "end": query.end.isoformat(),
                "limit": query.limit,
            },
            headers=headers,
        )
        try:
            response = LegacyTicketResponse.model_validate(payload)
        except ValidationError as exc:
            raise CapabilityMalformedResponse(
                "Legacy ticket response violated the synthetic contract"
            ) from exc
        records = [
            TicketRecord(
                **ticket.model_dump(exclude={"created_at", "resolved_at"}),
                created_at=ticket.created_at.astimezone(UTC),
                resolved_at=(
                    ticket.resolved_at.astimezone(UTC) if ticket.resolved_at else None
                ),
                source_reference=f"legacy-ticket:{ticket.id}",
            )
            for ticket in response.tickets
            if ticket.service == query.service
            and ticket.environment == query.environment
            and (query.status is None or ticket.status == query.status)
            and query.start <= ticket.created_at <= query.end
            and all(
                keyword.lower()
                in f"{ticket.title} {ticket.summary} {ticket.resolution or ''}".lower()
                for keyword in query.keywords
            )
        ]
        records.sort(key=lambda item: (item.created_at, item.id), reverse=True)
        return tuple(records[: query.limit])
