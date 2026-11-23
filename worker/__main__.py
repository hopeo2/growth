"""Entrypoint: poll the worker API, claim jobs, and run InstaPy.

Usage:

    python -m worker

Environment (see `.env.example`):

    WORKER_API_TOKEN, CREDENTIALS_ENCRYPTION_KEY, WORKER_API_URL/APP_ORIGIN,
    WORKER_NAME, WORKER_POLL_SECONDS, WORKER_CONCURRENCY, INSTAPY_PATH,
    WORKER_HEADLESS
"""

from __future__ import annotations

import logging
import signal
import sys
import time
from types import FrameType

from .api import ApiError, WorkerApi
from .config import load_config
from .runner import JobRunner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
)
logger = logging.getLogger("growly.worker")

_shutdown = False


def _handle_signal(signum: int, _frame: FrameType | None) -> None:
    global _shutdown
    logger.info("Received signal %s — finishing current job then exiting", signum)
    _shutdown = True


def main() -> int:
    config = load_config()
    api = WorkerApi(
        config.api_url, config.api_token, config.worker_name, config.version
    )
    runner = JobRunner(config, api)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    logger.info(
        "Worker '%s' v%s starting against %s (poll=%ss, headless=%s)",
        config.worker_name,
        config.version,
        config.api_url,
        config.poll_seconds,
        config.headless,
    )

    empty_polls = 0
    while not _shutdown:
        try:
            api.heartbeat(status="idle")
            response = api.claim()
        except ApiError as exc:
            logger.warning("Claim failed: %s", exc)
            _sleep(config.poll_seconds)
            continue

        job = response.get("job")
        account = response.get("account")

        if not job or not account:
            empty_polls += 1
            # Back off a little when the queue stays empty.
            _sleep(min(config.poll_seconds * (1 + empty_polls // 10), 120))
            continue

        empty_polls = 0
        job_id = job.get("id", "?")
        logger.info(
            "Claimed job %s (type=%s, account=@%s)",
            job_id,
            job.get("type"),
            account.get("username"),
        )

        try:
            report = runner.run(job, account)
            api.complete(job_id, report)
            logger.info("Job %s completed: %s", job_id, report.get("stats"))
        except Exception as exc:  # noqa: BLE001 - report any failure and continue
            logger.exception("Job %s failed", job_id)
            try:
                api.fail(job_id, f"{type(exc).__name__}: {exc}")
            except ApiError as api_exc:
                logger.error("Could not report failure for %s: %s", job_id, api_exc)

    logger.info("Worker stopped")
    return 0


def _sleep(seconds: float) -> None:
    # Wake up early if a signal arrives.
    deadline = time.monotonic() + max(1.0, seconds)
    while not _shutdown and time.monotonic() < deadline:
        time.sleep(min(1.0, deadline - time.monotonic()))


if __name__ == "__main__":
    sys.exit(main())
