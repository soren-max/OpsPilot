import argparse

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.memory.factory import build_memory_store
from app.memory.service import IncidentMemoryIndexer


def main() -> None:
    parser = argparse.ArgumentParser(description="Index eligible resolved incidents")
    parser.add_argument("--incident-id")
    parser.add_argument("--reindex", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    store = build_memory_store(settings)
    if store is None:
        parser.error("OPSPILOT_MEMORY_BACKEND must be qdrant")
    with SessionLocal() as db:
        indexer = IncidentMemoryIndexer(db, store, "deterministic-hash:1")
        result = indexer.index_one(args.incident_id) if args.incident_id else indexer.index_all()
    mode = "reindex" if args.reindex else "index"
    print(f"memory {mode} complete: indexed={result.indexed} embedding={result.embedding_version}")


if __name__ == "__main__":
    main()
