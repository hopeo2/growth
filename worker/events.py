"""Map InstaPy log records to activity events and batch them to the API."""

from __future__ import annotations

import logging
import re
from typing import Any

from .api import ApiError, WorkerApi

FOLLOW_RE = re.compile(r"Followed '(?P<target>[^']+)'!")
UNFOLLOW_RE = re.compile(r"Unfollowed '(?P<target>[^']+)'!")
LIKED_RE = re.compile(r"--> (?P<target>\S+) liked!")

MAX_EVENTS = 2000


def classify(message: str) -> tuple[str, str | None]:
    """Return `(action, target)` for a log message."""
    if "Logged in successfully" in message:
        return "login", None

    match = FOLLOW_RE.search(message)
    if match:
        return "follow", match.group("target")

    match = UNFOLLOW_RE.search(message)
    if match:
        return "unfollow", match.group("target")

    if "Commented:" in message:
        return "comment", None

    if "Watching stories" in message or "Watched" in message and "stor" in message:
        return "story", None

    if "Already following" in message or "already followed" in message.lower():
        return "info", None

    match = LIKED_RE.search(message)
    if match and "already liked" not in message:
        target = match.group("target")
        return "like", target if len(target) <= 200 else None

    return "info", None


class EventSink:
    """Buffers events and flushes them to the worker API."""

    def __init__(
        self,
        api: WorkerApi,
        job_id: str,
        flush_threshold: int = 25,
    ) -> None:
        self._api = api
        self._job_id = job_id
        self._threshold = flush_threshold
        self._buffer: list[dict[str, Any]] = []
        self._sent = 0
        self._dropped = 0
        self._counts: dict[str, int] = {}

    @property
    def stats(self) -> dict[str, int]:
        return {"sent": self._sent, "dropped": self._dropped}

    @property
    def counts(self) -> dict[str, int]:
        """Number of events recorded per action, including buffered ones."""
        return dict(self._counts)

    def add(
        self,
        action: str,
        message: str | None = None,
        target: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        if self._sent + len(self._buffer) >= MAX_EVENTS:
            self._dropped += 1
            return

        self._counts[action] = self._counts.get(action, 0) + 1
        self._buffer.append(
            {
                "action": action,
                "target": target,
                "message": (message or "")[:500] or None,
                "detail": detail or {},
            }
        )
        if len(self._buffer) >= self._threshold:
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return
        batch, self._buffer = self._buffer, []
        try:
            self._sent += self._api.send_events(self._job_id, batch)
        except ApiError as exc:
            # Put the events back so a later flush can retry, but don't let a
            # network hiccup abort the automation run.
            logging.getLogger("growly.worker.events").warning(
                "Could not deliver %d events: %s", len(batch), exc
            )
            if len(self._buffer) + len(batch) < MAX_EVENTS:
                self._buffer = batch + self._buffer


class InstaPyLogHandler(logging.Handler):
    """A `logging.Handler` passed to `InstaPy(log_handler=...)`."""

    def __init__(self, sink: EventSink) -> None:
        super().__init__(level=logging.INFO)
        self._sink = sink

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - never break InstaPy logging
            return

        if record.levelno >= logging.ERROR:
            action, target = "error", None
        elif record.levelno >= logging.WARNING:
            action, target = "warning", None
        else:
            action, target = classify(message)

        if action == "info" and not message.strip():
            return

        self._sink.add(
            action,
            message=message,
            target=target,
            detail={"level": record.levelname},
        )