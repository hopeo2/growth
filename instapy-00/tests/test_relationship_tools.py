"""Tests for the Instagram web API based relationship helpers."""

import instapy.relationship_tools as relationship_tools
from instapy.util import is_page_available


class _Response:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


class _Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(params)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class _Browser:
    def __init__(self, cookies=None):
        self.cookies = cookies or []

    def get_cookies(self):
        return self.cookies


class _Logger:
    def __init__(self):
        self.messages = []

    def info(self, message):
        self.messages.append(message)

    def warning(self, message):
        self.messages.append(message)


def _no_sleep(*args, **kwargs):
    return None


def test_relationship_usernames_paginates_and_removes_duplicates(monkeypatch):
    monkeypatch.setattr(relationship_tools, "update_activity", _no_sleep)
    monkeypatch.setattr(relationship_tools, "sleep", _no_sleep)

    session = _Session(
        [
            _Response(
                {
                    "users": [{"username": "a"}, {"username": "b"}],
                    "next_max_id": "cursor",
                }
            ),
            _Response(
                {
                    "users": [{"username": "b"}, {"username": "c"}],
                    "next_max_id": None,
                }
            ),
        ]
    )

    usernames = relationship_tools._get_relationship_usernames(
        _Browser(), session, {}, "1", "followers", "full", _Logger()
    )

    assert usernames == ["a", "b", "c"]
    assert session.calls == [{"count": 50}, {"count": 50, "max_id": "cursor"}]


def test_relationship_usernames_stops_at_requested_amount(monkeypatch):
    monkeypatch.setattr(relationship_tools, "update_activity", _no_sleep)

    session = _Session(
        [
            _Response(
                {
                    "users": [
                        {"username": "a"},
                        {"username": "b"},
                        {"username": "c"},
                    ],
                    "next_max_id": "cursor",
                }
            )
        ]
    )

    usernames = relationship_tools._get_relationship_usernames(
        _Browser(), session, {}, "1", "followers", 2, _Logger()
    )

    assert usernames == ["a", "b"]
    assert len(session.calls) == 1


def test_relationship_usernames_discards_partial_full_results(monkeypatch):
    monkeypatch.setattr(relationship_tools, "update_activity", _no_sleep)
    monkeypatch.setattr(relationship_tools, "sleep", _no_sleep)

    session = _Session(
        [
            _Response(
                {
                    "users": [{"username": "a"}],
                    "next_max_id": "cursor",
                }
            ),
            _Response({}, status_code=500),
        ]
    )

    usernames = relationship_tools._get_relationship_usernames(
        _Browser(), session, {}, "1", "followers", "full", _Logger()
    )

    assert usernames == []


def test_relationship_usernames_filters_unverified_users(monkeypatch):
    monkeypatch.setattr(relationship_tools, "update_activity", _no_sleep)

    session = _Session(
        [
            _Response(
                {
                    "users": [
                        {"username": "a", "is_verified": True},
                        {"username": "b", "is_verified": False},
                    ],
                    "next_max_id": None,
                }
            )
        ]
    )

    usernames = relationship_tools._get_relationship_usernames(
        _Browser(),
        session,
        {},
        "1",
        "followers",
        "full",
        _Logger(),
        verified_only=True,
    )

    assert usernames == ["a"]


def test_resolve_user_id_prefers_the_logged_in_cookie():
    browser = _Browser([{"name": "ds_user_id", "value": "12345"}])

    user_id = relationship_tools._resolve_user_id(
        browser, "tester", "tester", None, _Logger()
    )

    assert user_id == "12345"


def test_is_page_available_detects_removed_profile_message():
    class _Body:
        text = (
            "Sorry, this page isn't available. The link you followed may be "
            "broken, or the page may have been removed."
        )

    class _UnavailableBrowser:
        def find_element(self, by, value):
            return _Body()

    logger = _Logger()

    assert is_page_available(_UnavailableBrowser(), logger) is False
    assert any("isn't available" in message for message in logger.messages)