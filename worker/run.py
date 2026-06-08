from __future__ import annotations

import logging
import time

from app.config import get_settings
from app.db import connect, init_db
from app.jobs import run_next_job


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("seedvr2-worker")


def main() -> None:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    for child in ("input", "output", "work", "logs"):
        (settings.data_dir / child).mkdir(parents=True, exist_ok=True)

    LOGGER.info("Worker started. mock_pipeline=%s data_dir=%s", settings.mock_pipeline, settings.data_dir)
    while True:
        with connect(settings) as conn:
            init_db(conn)
            job_id = run_next_job(conn, settings)
        if job_id is None:
            time.sleep(2.0)
        else:
            LOGGER.info("Finished job %s", job_id)


if __name__ == "__main__":
    main()

