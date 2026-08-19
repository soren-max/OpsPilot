from typing import Protocol

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver


class CheckpointBackend(Protocol):
    @property
    def name(self) -> str: ...

    def create(self) -> BaseCheckpointSaver[str]: ...


class MemoryCheckpointBackend:
    """Development/test only. M4 will provide durable Postgres checkpoint persistence."""

    name = "memory"

    def __init__(self) -> None:
        self._saver = InMemorySaver()

    def create(self) -> BaseCheckpointSaver[str]:
        return self._saver
