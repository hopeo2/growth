"""Tests for the per-task options and per-task cooldown."""

import contextlib
import sys
import time
from datetime import datetime, timedelta
from types import SimpleNamespace

import hashtag_engagement as he


def _task_args(**overrides):
    values = dict(
        task_all=False,
        task_hashtags=False,
        task_unfollow=False,
        task_comments=False,
        task_stories=False,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _state(**hours_ago):
    now = datetime.now()
    return {
        "last_run_by_task": {
            task: (now - timedelta(hours=hours)).isoformat()
            for task, hours in hours_ago.items()
        }
    }


def test_no_task_flag_selects_every_task():
    assert he.selected_tasks(_task_args()) == set(he.ALL_TASKS)


def test_all_tasks_flag_selects_every_task():
    args = _task_args(task_all=True, task_unfollow=True)
    assert he.selected_tasks(args) == set(he.ALL_TASKS)


def test_individual_flags_select_only_those_tasks():
    args = _task_args(task_unfollow=True, task_stories=True)
    assert he.selected_tasks(args) == {he.TASK_UNFOLLOW, he.TASK_STORIES}


def test_cooldown_is_tracked_per_task():
    state = _state(hashtags=1, unfollow=10)

    # The hashtag task ran one hour ago, so a 3 hour cooldown blocks it.
    assert he.check_run_gap(state, 3, {he.TASK_HASHTAGS}) is False

    # The unfollow task ran ten hours ago, so it is allowed even though the
    # hashtag task ran recently.
    assert he.check_run_gap(state, 3, {he.TASK_UNFOLLOW}) is True


def test_never_run_task_is_not_blocked_by_other_tasks():
    state = _state(hashtags=0)
    assert he.check_run_gap(state, 3, {he.TASK_STORIES}) is True


def test_legacy_state_applies_to_every_task_once():
    state = {"last_run": (datetime.now() - timedelta(hours=1)).isoformat()}
    assert he.check_run_gap(state, 3, {he.TASK_UNFOLLOW}) is False


def test_tasks_without_allowance_reports_capped_tasks():
    args = SimpleNamespace(
        max_likes_daily=10,
        max_comments_daily=10,
        max_follows_daily=10,
        max_unfollows_daily=5,
        like_comments_accounts=2,
        unfollow_after_days=3,
    )
    usage = {"likes": 10, "comments": 0, "follows": 0, "unfollows": 5}

    blocked = he.tasks_without_allowance(usage, args, set(he.ALL_TASKS))

    assert set(blocked) == {
        he.TASK_HASHTAGS,
        he.TASK_COMMENTS,
        he.TASK_UNFOLLOW,
    }


def test_stories_are_never_capped():
    args = SimpleNamespace(
        max_likes_daily=10,
        max_comments_daily=10,
        max_follows_daily=10,
        max_unfollows_daily=5,
        like_comments_accounts=2,
        unfollow_after_days=3,
    )
    usage = {"likes": 10, "comments": 10, "follows": 10, "unfollows": 5}

    assert he.tasks_without_allowance(usage, args, {he.TASK_STORIES}) == []


class _FakeBrowser:
    def set_window_size(self, *args):
        return None


class _FakeSession:
    def __init__(self, **kwargs):
        self.logfolder = "/tmp"
        self.browser = _FakeBrowser()

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


def _run_session_args(tasks):
    args = SimpleNamespace(
        headless=False,
        max_follow_difference=5000,
        follow_percentage=80,
        comment_percentage=50,
        reply_percentage=30,
        story_accounts=2,
        max_post_age_days=7,
        max_likes_hourly=25,
        max_likes_daily=80,
        max_comments_hourly=5,
        max_comments_daily=15,
        max_follows_hourly=10,
        max_follows_daily=30,
        max_unfollows_hourly=10,
        max_unfollows_daily=30,
    )
    args.tasks = set(tasks)
    return args


def test_run_session_only_calls_the_selected_tasks(monkeypatch):
    called = []

    monkeypatch.setattr(
        he, "unfollow_nonfollowers", lambda *call: called.append("unfollow")
    )
    monkeypatch.setattr(
        he, "run_story_engagement", lambda *call: called.append("stories")
    )
    monkeypatch.setattr(
        he, "run_comment_engagement", lambda *call: called.append("comments")
    )
    monkeypatch.setattr(
        he, "today_usage", lambda username: {"likes": 0, "comments": 0}
    )
    monkeypatch.setattr(he, "InstaPy", lambda **kwargs: _FakeSession())
    monkeypatch.setattr(
        he, "smart_run", lambda session: contextlib.nullcontext()
    )

    he.run_session(
        _run_session_args({he.TASK_UNFOLLOW}),
        ["tag"],
        ["comment"],
        ["reply"],
        "tester",
        None,
    )

    assert called == ["unfollow"]


# ---------------------------------------------------------------------------
# Interactive setup
# ---------------------------------------------------------------------------


def _feed(monkeypatch, answers):
    """Make ``input()`` return the given answers in order."""
    answers = iter(answers)

    def fake_input(prompt=""):
        return next(answers)

    monkeypatch.setattr("builtins.input", fake_input)


def _parse(monkeypatch, argv=None):
    monkeypatch.setattr(sys, "argv", argv or ["hashtag_engagement.py"])
    return he.parse_args()


def test_interactive_menu_selects_tasks_and_values(monkeypatch):
    args = _parse(monkeypatch)

    # Task 2 (unfollow), wait 4 days, then keep every other default.
    _feed(monkeypatch, ["2", "4", "10"] + [""] * 60)
    he.run_interactive(args)

    assert args.tasks == {he.TASK_UNFOLLOW}
    assert args.unfollow_after_days == 4
    assert args.max_post_age_days == 10


def test_interactive_zero_selects_every_task(monkeypatch):
    args = _parse(monkeypatch)

    _feed(monkeypatch, ["0"] + [""] * 60)
    he.run_interactive(args)

    assert args.tasks == set(he.ALL_TASKS)


def test_interactive_retries_invalid_task_choice(monkeypatch):
    args = _parse(monkeypatch)

    _feed(monkeypatch, ["nonsense", "3"] + [""] * 60)
    he.run_interactive(args)

    # The invalid first answer is ignored and "3" selects the comment task.
    assert args.tasks == {he.TASK_COMMENTS}


def test_should_prompt_skips_dry_run_interactive_and_task_flags(monkeypatch):
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(isatty=lambda: True))

    base = dict(dry_run=False, no_interactive=False, tasks_explicit=False)
    assert he.should_prompt(SimpleNamespace(**base)) is True
    assert (
        he.should_prompt(SimpleNamespace(dry_run=True, no_interactive=False,
                                         tasks_explicit=False))
        is False
    )
    assert (
        he.should_prompt(SimpleNamespace(dry_run=False, no_interactive=True,
                                         tasks_explicit=False))
        is False
    )
    assert (
        he.should_prompt(SimpleNamespace(dry_run=False, no_interactive=False,
                                         tasks_explicit=True))
        is False
    )


def test_should_prompt_needs_a_terminal(monkeypatch):
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(isatty=lambda: False))
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(isatty=lambda: True))
    args = SimpleNamespace(dry_run=False, no_interactive=False, tasks_explicit=False)
    assert he.should_prompt(args) is False


def test_task_flags_mark_the_selection_as_explicit(monkeypatch):
    args = _parse(monkeypatch, ["hashtag_engagement.py", "--stories"])
    assert args.tasks == {he.TASK_STORIES}
    assert args.tasks_explicit is True

    args = _parse(monkeypatch, ["hashtag_engagement.py"])
    assert args.tasks_explicit is False