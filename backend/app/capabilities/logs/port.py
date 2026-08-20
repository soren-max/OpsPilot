from typing import Protocol

from app.capabilities.logs.models import LogObservation, LogQuery


class LogsCapability(Protocol):
    async def query(self, query: LogQuery) -> LogObservation: ...
