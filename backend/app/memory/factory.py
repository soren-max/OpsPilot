from app.adapters.qdrant import QdrantIncidentMemory
from app.core.config import Settings
from app.domain.incidents.memory import IncidentMemoryStore
from app.memory.embedding import DeterministicHashEmbedding


def build_memory_store(settings: Settings) -> IncidentMemoryStore | None:
    if settings.memory_backend == "disabled":
        return None
    if settings.qdrant_base_url is None:
        raise ValueError("Qdrant base URL is required")
    embedding = DeterministicHashEmbedding()
    return QdrantIncidentMemory(
        settings.qdrant_base_url,
        settings.qdrant_collection,
        embedding,
        api_key=(settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None),
    )
