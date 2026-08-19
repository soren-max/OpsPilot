from __future__ import annotations

import logging
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def wait_for_database() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    deadline = time.monotonic() + 120
    attempt = 0
    try:
        while True:
            attempt += 1
            try:
                with engine.connect() as connection:
                    connection.execute(text("SELECT 1"))
                logger.info("Database is ready after %s connection attempt(s)", attempt)
                return
            except SQLAlchemyError as exc:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Database did not become ready within 120 seconds") from exc
                logger.warning("Database is not ready; retrying in 2 seconds")
                time.sleep(2)
    finally:
        engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    wait_for_database()
