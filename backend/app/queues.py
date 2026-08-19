from typing import Protocol


class TaskQueue(Protocol):
    def enqueue(self, task_id: str) -> None: ...

    def dequeue(self) -> str | None: ...


class MemoryQueue:
    def __init__(self) -> None:
        self._items: list[str] = []

    def enqueue(self, task_id: str) -> None:
        if task_id not in self._items:
            self._items.append(task_id)

    def dequeue(self) -> str | None:
        return self._items.pop(0) if self._items else None


class RedisQueue:
    """Adapter boundary only; no Redis client or connection is created in v0.3.0."""

    def __init__(self, redis_url: str | None, queue_name: str) -> None:
        self.redis_url = redis_url
        self.queue_name = queue_name

    def enqueue(self, task_id: str) -> None:
        raise RuntimeError("RedisQueue is not connected in v0.3.0 operations framework")

    def dequeue(self) -> str | None:
        raise RuntimeError("RedisQueue is not connected in v0.3.0 operations framework")
