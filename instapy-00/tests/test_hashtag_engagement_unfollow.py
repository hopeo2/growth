"""Tests for the unfollow helpers in the hashtag engagement script."""

import os
from types import SimpleNamespace

import hashtag_engagement as he
from hashtag_engagement import followed_pool_usernames, remaining_unfollows


class _FakeSession:
    def __init__(self, logfolder, remove=()):
        self.logfolder = str(logfolder)
        self.logger = object()
        self.calls = []
        self.remove = set(remove)

    def unfollow_users(self, **kwargs):
        self.calls.append(kwargs)
        path = os.path.join(self.logfolder, "tester_followedPool.csv")
        with open(path, encoding="utf-8") as file_handle:
            rows = file_handle.readlines()
        with open(path, "w", encoding="utf-8") as file_handle:
            for row in rows:
                username = row.split(" ~ ")[1].strip().rstrip(",")
                if username not in self.remove:
                    file_handle.write(row)


def _write_pool(tmp_path, *usernames):
    (tmp_path / "tester_followedPool.csv").write_text(
        "".join(
            "2026-01-01 10:00 ~ {} ~ 111,\n".format(name)
            for name in usernames
        ),
        encoding="utf-8",
    )


def test_followed_pool_usernames_parses_current_and_legacy_rows(tmp_path):
    (tmp_path / "tester_followedPool.csv").write_text(
        "2026-01-01 10:00 ~ alice ~ 111,\n"
        "bob,\n"
        "2026-01-02 11:00 ~ carol ~ 222,\n",
        encoding="utf-8",
    )

    users = followed_pool_usernames(str(tmp_path), "tester")

    assert users == {"alice", "bob", "carol"}


def test_followed_pool_usernames_returns_empty_set_when_missing(tmp_path):
    assert followed_pool_usernames(str(tmp_path), "tester") == set()


def test_remaining_unfollows_respects_daily_cap():
    args = SimpleNamespace(max_unfollows_daily=30)

    assert remaining_unfollows({"unfollows": 10}, args) == 20
    assert remaining_unfollows({"unfollows": 30}, args) == 0
    assert remaining_unfollows({"unfollows": 45}, args) == 0


def test_unfollow_nonfollowers_restricts_removed_users(tmp_path, monkeypatch):
    _write_pool(tmp_path, "alice", "bob")
    session = _FakeSession(tmp_path, remove={"alice"})
    args = SimpleNamespace(unfollow_after_days=3, max_unfollows_daily=30)
    restricted = []

    monkeypatch.setattr(he, "today_usage", lambda username: {"unfollows": 0})
    monkeypatch.setattr(
        he, "follow_restriction", lambda *call: restricted.append(call)
    )

    removed = he.unfollow_nonfollowers(session, args, "tester")

    assert removed == {"alice"}
    assert restricted == [("write", "alice", None, session.logger)]
    assert session.calls == [
        {
            "amount": 30,
            "nonFollowers": True,
            "style": "FIFO",
            "unfollow_after": 3 * 24 * 60 * 60,
            "sleep_delay": 600,
        }
    ]


def test_unfollow_nonfollowers_disabled_does_nothing(tmp_path):
    session = _FakeSession(tmp_path)
    args = SimpleNamespace(unfollow_after_days=0, max_unfollows_daily=30)

    assert he.unfollow_nonfollowers(session, args, "tester") == set()
    assert session.calls == []


def test_unfollow_nonfollowers_stops_at_daily_cap(tmp_path, monkeypatch):
    session = _FakeSession(tmp_path)
    args = SimpleNamespace(unfollow_after_days=3, max_unfollows_daily=30)

    monkeypatch.setattr(he, "today_usage", lambda username: {"unfollows": 30})

    assert he.unfollow_nonfollowers(session, args, "tester") == set()
    assert session.calls == []
