from functools import lru_cache

import psycopg
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_workflow_checkpointer() -> BaseCheckpointSaver[str]:
    """Return the process checkpointer; production PostgreSQL survives worker restarts."""
    settings = get_settings()
    backend = settings.workflow_checkpoint_backend
    if backend == "memory" or (
        backend == "auto" and not settings.database_url.startswith("postgres")
    ):
        return InMemorySaver()
    if not settings.database_url.startswith("postgres"):
        raise ValueError("PostgreSQL workflow checkpoints require a PostgreSQL database URL")
    connection_url = settings.database_url.replace(
        "postgresql+psycopg://", "postgresql://", 1
    )
    connection = psycopg.connect(
        connection_url, autocommit=True, prepare_threshold=0, row_factory=dict_row
    )
    saver = PostgresSaver(connection)
    saver.setup()
    return saver
