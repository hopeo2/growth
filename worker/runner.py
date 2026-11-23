"""Build and execute InstaPy runs for claimed jobs."""

from __future__ import annotations

import logging
import math
import sys
from typing import Any
from urllib.parse import unquote, urlparse

from .api import WorkerApi
from .config import Config
from .crypto import decrypt_secret
from .events import EventSink, InstaPyLogHandler

logger = logging.getLogger("growly.worker.runner")


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _per_run_limit(daily_cap: int, runs_per_day: int, fallback: int) -> int:
    if daily_cap <= 0:
        return 0
    runs = max(1, runs_per_day)
    budget = math.ceil(daily_cap / runs)
    return max(1, min(fallback, budget))


def _parse_proxy(proxy_url: str | None) -> dict[str, Any]:
    if not proxy_url:
        return {}
    parsed = urlparse(proxy_url if "://" in proxy_url else f"http://{proxy_url}")
    if not parsed.hostname or not parsed.port:
        logger.warning("Ignoring unparseable proxy URL: %s", proxy_url)
        return {}
    if parsed.scheme not in {"http", "https"}:
        logger.warning(
            "InstaPy only supports HTTP(S) proxies; '%s' may not work",
            parsed.scheme,
        )
    return {
        "proxy_address": parsed.hostname,
        "proxy_port": parsed.port,
        "proxy_username": unquote(parsed.username) if parsed.username else None,
        "proxy_password": unquote(parsed.password) if parsed.password else None,
    }


def _reset_logger(username: str, settings: Any) -> None:
    """Detach every handler from the per-username logger InstaPy reuses.

    ``logging.getLogger`` returns the same object for a given name for the whole
    process, so unless handlers are cleared, each run would add another file
    handler and another event handler, duplicating activity.
    """
    settings.loggers.pop(username, None)
    if not username:
        return
    logger = logging.getLogger(username)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:  # noqa: BLE001 - closing is best-effort
            pass


def _load_instapy(config: Config):
    path = str(config.instapy_path)
    if path not in sys.path:
        sys.path.insert(0, path)
    try:
        from instapy import InstaPy  # type: ignore import-not-found
        from instapy.settings import Settings  # type: ignore import-not-found
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            f"InstaPy could not be imported from {path}. "
            "Install its requirements first (see worker/README.md)."
        ) from exc
    return InstaPy, Settings


class JobRunner:
    def __init__(self, config: Config, api: WorkerApi) -> None:
        self._config = config
        self._api = api

    def run(self, job: dict[str, Any], account: dict[str, Any]) -> dict[str, Any]:
        job_type = job.get("type", "growth_run")
        payload = job.get("payload") or {}
        username = account.get("username") or payload.get("account", {}).get(
            "username", ""
        )

        password = decrypt_secret(
            account["credentials"], self._config.encryption_key
        )

        InstaPy, Settings = _load_instapy(self._config)
        sink = EventSink(self._api, job["id"])
        handler = InstaPyLogHandler(sink)

        def progress(percent: int) -> None:
            sink.flush()
            try:
                self._api.progress(job["id"], _clamp(percent, 0, 100))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Progress update failed: %s", exc)

        progress(5)

        # InstaPy caches loggers per username in `Settings.loggers`, but the
        # underlying `logging` logger is global and would keep accumulating
        # handlers across runs. Reset both so our handler is attached once.
        _reset_logger(username, Settings)

        proxy = _parse_proxy(
            account.get("proxyUrl")
            or payload.get("account", {}).get("proxyUrl")
            or self._config.default_proxy
        )
        if proxy:
            logger.info(
                "Routing @%s through proxy %s:%s",
                username,
                proxy.get("proxy_address"),
                proxy.get("proxy_port"),
            )
        else:
            logger.info("Running @%s without a proxy", username)

        instapy = None
        report: dict[str, Any]
        try:
            instapy = InstaPy(
                username=username,
                password=password,
                headless_browser=self._config.headless,
                show_logs=False,
                log_handler=handler,
                **proxy,
            )

            instapy.login()
            if getattr(instapy, "aborting", False):
                raise RuntimeError(
                    "Instagram login failed. Check the credentials or proxy."
                )

            progress(15)

            if job_type == "growth_run":
                report = self._run_growth(
                    instapy, payload, sink, progress
                )
            else:
                # `login_check` and `account_sync` only verify the session and
                # refresh the follower counts.
                sink.add("login", message=f"Logged in as @{username}")
                report = self._build_report(instapy, sink, {})

            progress(100)
        finally:
            sink.flush()
            if instapy is not None:
                try:
                    instapy.end()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("InstaPy shutdown failed: %s", exc)
            _reset_logger(username, Settings)

        report["result"] = {
            "jobType": job_type,
            "events": sink.stats,
        }
        return report

    # -- growth ------------------------------------------------------------

    def _run_growth(
        self,
        instapy: Any,
        payload: dict[str, Any],
        sink: EventSink,
        progress: Any,
    ) -> dict[str, Any]:
        settings = payload.get("settings") or {}
        targets = payload.get("targets") or {}

        hashtags = list(targets.get("hashtags") or [])
        users = list(targets.get("users") or [])
        locations = list(targets.get("locations") or [])

        runs_per_day = int(settings.get("runsPerDay") or 4)
        interactions = int(settings.get("interactionsPerRun") or 30)
        likes_amount = _per_run_limit(
            int(settings.get("likesPerDay") or 0), runs_per_day, interactions
        )
        follows_amount = _per_run_limit(
            int(settings.get("followsPerDay") or 0), runs_per_day, interactions
        )
        comments_amount = _per_run_limit(
            int(settings.get("commentsPerDay") or 0), runs_per_day, interactions
        )
        stories_amount = _per_run_limit(
            int(settings.get("storiesPerDay") or 0), runs_per_day, interactions
        )
        unfollows_amount = _per_run_limit(
            int(settings.get("unfollowsPerDay") or 0), runs_per_day, 200
        )

        self._configure(instapy, settings, hashtags, locations)

        actions = 0
        total_phases = 1
        phase = 0

        def step() -> None:
            nonlocal phase
            phase += 1
            progress(15 + int(75 * phase / total_phases))

        phases: list[tuple[str, Any]] = []

        if hashtags and settings.get("likeByTags", True) and likes_amount > 0:
            phases.append(
                (
                    "like_by_tags",
                    lambda: instapy.like_by_tags(
                        hashtags,
                        amount=likes_amount,
                        skip_top_posts=True,
                        randomize=True,
                    ),
                )
            )

        if hashtags and settings.get("followByTags"):
            phases.append(
                (
                    "follow_by_tags",
                    lambda: instapy.follow_by_tags(
                        hashtags, amount=follows_amount, randomize=True
                    ),
                )
            )

        if users and settings.get("interactByUsers"):
            phases.append(
                (
                    "interact_by_users",
                    lambda: instapy.interact_by_users(
                        users, amount=follows_amount or interactions, randomize=True
                    ),
                )
            )

        if locations:
            phases.append(
                (
                    "like_by_locations",
                    lambda: instapy.like_by_locations(
                        locations, amount=likes_amount, randomize=True
                    ),
                )
            )

        if hashtags and settings.get("watchStories") and stories_amount > 0:
            phases.append(
                ("story_by_tags", lambda: instapy.story_by_tags(hashtags))
            )

        if settings.get("unfollowEnabled") and unfollows_amount > 0:
            phases.append(
                (
                    "unfollow_users",
                    lambda: instapy.unfollow_users(
                        amount=unfollows_amount,
                        nonFollowers=True,
                        sleep_delay=60,
                    ),
                )
            )

        total_phases = max(1, len(phases))
        for name, action in phases:
            sink.add("info", message=f"Starting {name}")
            try:
                action()
            except Exception as exc:  # noqa: BLE001
                sink.add(
                    "error",
                    message=f"{name} failed: {exc}",
                    detail={"phase": name},
                )
                logger.exception("Phase %s failed", name)
            step()
            actions += 1

        if not phases:
            sink.add(
                "warning",
                message=(
                    "Nothing to run: enable an activity and add at least one "
                    "hashtag or target."
                ),
            )

        # `commentsPerDay` is enforced by InstaPy's comment percentage; use it
        # only to annotate the report so the UI can show the budget.
        return self._build_report(
            instapy,
            sink,
            {
                "phases": [name for name, _ in phases],
                "budget": {
                    "likes": likes_amount,
                    "follows": follows_amount,
                    "comments": comments_amount,
                    "stories": stories_amount,
                    "unfollows": unfollows_amount,
                },
            },
        )

    def _configure(
        self,
        instapy: Any,
        settings: dict[str, Any],
        hashtags: list[str],
        locations: list[str],
    ) -> None:
        comments = [c for c in (settings.get("comments") or []) if c.strip()]
        blacklist = list(settings.get("blacklistTags") or [])
        ignore_users = list(settings.get("ignoreUsers") or [])
        dont_include = list(settings.get("dontIncludeUsers") or [])

        delay_min = int(settings.get("actionDelayMinSec") or 2)
        delay_max = int(settings.get("actionDelayMaxSec") or delay_min)
        if delay_max < delay_min:
            delay_max = delay_min

        instapy.set_action_delays(
            enabled=True,
            like=delay_min,
            comment=delay_min,
            follow=delay_min,
            unfollow=delay_min,
            story=delay_min,
            randomize=True,
            random_range_from=delay_min,
            random_range_to=delay_max,
            safety_match=False,
        )

        instapy.set_do_like(
            enabled=bool(settings.get("likeByTags", True)), percentage=100
        )
        instapy.set_do_follow(
            enabled=bool(settings.get("followByTags")),
            percentage=int(settings.get("followPercentage") or 0),
        )
        instapy.set_do_comment(
            enabled=bool(comments),
            percentage=int(settings.get("commentPercentage") or 0),
        )
        instapy.set_do_story(
            enabled=bool(settings.get("watchStories")), percentage=100
        )

        if comments:
            instapy.set_comments(comments)
        if blacklist:
            instapy.set_dont_like(blacklist)
        if ignore_users:
            instapy.set_ignore_users(ignore_users)
        if dont_include:
            instapy.set_dont_include(dont_include)

        instapy.set_user_interact(
            amount=int(settings.get("interactionsPerRun") or 30),
            percentage=100,
            randomize=True,
        )

        if settings.get("skipPrivateAccounts", True):
            instapy.set_skip_users(skip_private=True)

        max_post_age = settings.get("maxPostAgeDays")
        if max_post_age:
            instapy.set_max_post_age_days(int(max_post_age))

        bounds = {
            "min_followers": settings.get("minFollowers"),
            "max_followers": settings.get("maxFollowers"),
            "min_following": settings.get("minFollowing"),
            "max_following": settings.get("maxFollowing"),
        }
        if any(value is not None for value in bounds.values()):
            instapy.set_relationship_bounds(
                enabled=True,
                delimit_by_numbers=True,
                min_followers=bounds["min_followers"],
                max_followers=bounds["max_followers"],
                min_following=bounds["min_following"],
                max_following=bounds["max_following"],
            )

    # -- reporting ---------------------------------------------------------

    def _build_report(
        self, instapy: Any, sink: EventSink, extra: dict[str, Any]
    ) -> dict[str, Any]:
        stats = {
            "likes": _as_int(getattr(instapy, "liked_img", 0)) or 0,
            "follows": _as_int(getattr(instapy, "followed", 0)) or 0,
            "unfollows": _as_int(getattr(instapy, "unfollowed", 0)) or 0,
            "comments": _as_int(getattr(instapy, "commented", 0)) or 0,
            "stories": _as_int(getattr(instapy, "stories_watched", 0)) or 0,
            "errors": sink.counts.get("error", 0),
        }
        return {
            "stats": stats,
            "followers": _as_int(getattr(instapy, "followed_by", 0)),
            "following": _as_int(getattr(instapy, "following_num", 0)),
            "posts": None,
            **extra,
        }