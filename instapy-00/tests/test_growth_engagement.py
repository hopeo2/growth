"""Tests for the extra story/comment engagement phase."""

import time
from types import SimpleNamespace

import hashtag_engagement as he


class _FakeSession:
    def __init__(self, logfolder):
        self.logfolder = str(logfolder)
        self.calls = []

    def story_by_users(self, users):
        self.calls.append(("stories", list(users)))

    def interact_by_comments(self, **kwargs):
        self.calls.append(("comments", kwargs))


def _write_pool(tmp_path, *usernames):
    (tmp_path / "tester_followedPool.csv").write_text(
        "".join(
            "2026-01-01 10:00 ~ {} ~ 111,\n".format(name)
            for name in usernames
        ),
        encoding="utf-8",
    )


def _args(**overrides):
    values = dict(
        like_comments_accounts=2,
        like_comments_posts=1,
        like_comments_per_post=2,
        story_accounts=2,
        reply_percentage=30,
        max_run_minutes=45,
        max_likes_daily=80,
        max_comments_daily=15,
        max_follows_daily=30,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_growth_engagement_watches_stories_and_likes_comments(
    tmp_path, monkeypatch
):
    _write_pool(tmp_path, "alice", "bob", "carol")
    session = _FakeSession(tmp_path)

    monkeypatch.setattr(
        he,
        "today_usage",
        lambda username: {
            "likes": 0,
            "comments": 0,
            "follows": 0,
            "unfollows": 0,
        },
    )

    he.run_growth_engagement(session, _args(), "tester", time.monotonic())

    kinds = [call[0] for call in session.calls]
    assert kinds == ["stories", "comments"]

    stories = session.calls[0][1]
    assert len(stories) == 2
    assert set(stories) <= {"alice", "bob", "carol"}

    comment_call = session.calls[1][1]
    assert comment_call["posts_amount"] == 1
    assert comment_call["comments_per_post"] == 2
    assert comment_call["reply"] is True
    assert comment_call["interact"] is False
    assert len(comment_call["usernames"]) == 2


def test_growth_engagement_disabled_does_nothing(tmp_path):
    _write_pool(tmp_path, "alice")
    session = _FakeSession(tmp_path)
    args = _args(like_comments_accounts=0, story_accounts=0)

    he.run_growth_engagement(session, args, "tester", time.monotonic())

    assert session.calls == []


def test_growth_engagement_skips_comment_likes_at_daily_cap(
    tmp_path, monkeypatch
):
    _write_pool(tmp_path, "alice", "bob")
    session = _FakeSession(tmp_path)

    monkeypatch.setattr(
        he,
        "today_usage",
        lambda username: {
            "likes": 80,
            "comments": 0,
            "follows": 0,
            "unfollows": 0,
        },
    )

    he.run_growth_engagement(session, _args(), "tester", time.monotonic())

    assert [call[0] for call in session.calls] == ["stories"]


def test_growth_engagement_skips_when_run_time_is_over(tmp_path):
    _write_pool(tmp_path, "alice")
    session = _FakeSession(tmp_path)

    he.run_growth_engagement(
        session, _args(), "tester", time.monotonic() - 46 * 60
    )

    assert session.calls == []