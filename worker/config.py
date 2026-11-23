"""Worker configuration, loaded from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Best-effort load of the repo-root `.env` (if python-dotenv is present)."""
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return
    load_dotenv(env_file)


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(
            f"Missing required environment variable {name}. "
            "Copy .env.example to .env and fill it in."
        )
    return value


@dataclass(frozen=True)
class Config:
    api_url: str
    api_token: str
    encryption_key: str
    worker_name: str
    poll_seconds: float
    concurrency: int
    instapy_path: Path
    headless: bool
    version: str
    default_proxy: str | None


def load_config() -> Config:
    _load_dotenv()

    base_url = (
        os.getenv("WORKER_API_URL")
        or os.getenv("APP_ORIGIN")
        or "http://localhost:3000"
    ).rstrip("/")

    instapy_path = Path(os.getenv("INSTAPY_PATH", "./instapy-00"))
    if not instapy_path.is_absolute():
        instapy_path = (REPO_ROOT / instapy_path).resolve()

    return Config(
        api_url=base_url,
        api_token=_require("WORKER_API_TOKEN"),
        encryption_key=_require("CREDENTIALS_ENCRYPTION_KEY"),
        worker_name=os.getenv("WORKER_NAME", "worker-1"),
        poll_seconds=float(os.getenv("WORKER_POLL_SECONDS", "20")),
        concurrency=int(os.getenv("WORKER_CONCURRENCY", "1")),
        instapy_path=instapy_path,
        headless=os.getenv("WORKER_HEADLESS", "true").lower()
        in {"1", "true", "yes", "on"},
        version="0.1.0",
        default_proxy=(os.getenv("WORKER_DEFAULT_PROXY") or "").strip() or None,
    )
