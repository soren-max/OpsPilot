import signal
import time

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.executors.factory import build_executor
from app.services.worker import WorkerService

running = True


def stop_worker(_signum: int, _frame: object) -> None:
    global running
    running = False


def main() -> None:
    signal.signal(signal.SIGINT, stop_worker)
    signal.signal(signal.SIGTERM, stop_worker)
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_file)
    executor = build_executor(settings)
    while running:
        with SessionLocal() as db:
            handled = WorkerService(db, executor).run_once()
        if not handled:
            time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    main()
