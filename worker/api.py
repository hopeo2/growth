"""HTTP client for the web app's worker API (`/api/worker/*`)."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

logger = logging.getLogger("growly.worker.api")

RETRIES = 3
TIMEOUT = 30


class ApiError(RuntimeError):
    pass


class WorkerApi:
    def __init__(self, base_url: str, token: str, worker_name: str, version: str):
        self._base_url = base_url.rstrip("/")
        self._worker_name = worker_name
        self._version = version
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    # -- transport ---------------------------------------------------------

    def _post(self, action: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}/api/worker/{action}"
        payload = {"worker": self._worker_name, **body}
        last_error: Exception | None = None

        for attempt in range(1, RETRIES + 1):
            try:
                response = self._session.post(url, json=payload, timeout=TIMEOUT)
                if response.status_code == 401:
                    raise ApiError("Worker API rejected the token (401)")
                if response.status_code >= 500:
                    raise ApiError(
                        f"{action}: server error {response.status_code}"
                    )
                if not response.ok:
                    detail = response.text[:300]
                    raise ApiError(f"{action}: {response.status_code} {detail}")
                if not response.content:
                    return {}
                return response.json()
            except (requests.RequestException, ApiError) as exc:
                last_error = exc
                if attempt < RETRIES:
                    time.sleep(2 * attempt)
                    continue
                break

        raise ApiError(f"{action} failed: {last_error}")

    # -- endpoints ---------------------------------------------------------

    def heartbeat(
        self, status: str = "online", current_job_id: str | None = None
    ) -> dict[str, Any]:
        return self._post(
            "heartbeat",
            {
                "version": self._version,
                "concurrency": 1,
                "status": status,
                "currentJobId": current_job_id,
            },
        )

    def claim(self) -> dict[str, Any]:
        return self._post("claim", {})

    def progress(self, job_id: str, percent: int) -> None:
        self._post("progress", {"jobId": job_id, "progress": int(percent)})

    def send_events(
        self, job_id: str, events: list[dict[str, Any]]
    ) -> int:
        if not events:
            return 0
        result = self._post("events", {"jobId": job_id, "events": events})
        return int(result.get("inserted", 0))

    def complete(self, job_id: str, report: dict[str, Any]) -> None:
        self._post("complete", {"jobId": job_id, "report": report})

    def fail(self, job_id: str, error: str) -> None:
        self._post("fail", {"jobId": job_id, "error": error[:2000]})