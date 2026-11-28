"""Tests for the Instagram web API based relationship helpers."""

import json

import instapy.relationship_tools as relationship_tools
from instapy.util import is_page_available


class _Response:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


class _BadJSONResponse:
    """A 200 response whose body is an HTML page instead of JSON."""

    def __init__(self, body="<html>login required</html>", status_code=200):
        self.status_code = status_code
        self.headers = {"Content-Type": "text/html"}
        self.text = body

    def json(self):
        raise ValueError("not JSON")


class _AsyncBrowser:
    """A browser whose in-page requests return queued bodies."""

    def __init__(self, pages):
        self.pages = list(pages)
        self.scripts = []
        self.script_timeout = None

    def set_script_timeout(self, timeout):
        self.script_timeout = timeout

    def execute_async_script(self, script, *args):
        self.scripts.append((script, args))
        page = self.pages.pop(0)
        if isinstance(page, Exception):
            raise page
        return page


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


def test_relationship_usernames_falls_back_to_browser(monkeypatch):
    monkeypatch.setattr(relationship_tools, "update_activity", _no_sleep)
    monkeypatch.setattr(relationship_tools, "sleep", _no_sleep)

    session = _Session([_BadJSONResponse()])
    browser = _AsyncBrowser(
        [json.dumps({"users": [{"username": "a"}, {"username": "b"}]})]
    )

    usernames = relationship_tools._get_relationship_usernames(
        browser, session, {}, "1", "followers", "full", _Logger()
    )

    assert usernames == ["a", "b"]
    # the in-page request must target the same API path as the requests call
    script, args = browser.scripts[0]
    assert args[0] == "/api/v1/friendships/1/followers/?count=50"


def test_relationship_usernames_paginates_in_browser(monkeypatch):
    monkeypatch.setattr(relationship_tools, "update_activity", _no_sleep)
    monkeypatch.setattr(relationship_tools, "sleep", _no_sleep)

    session = _Session([_BadJSONResponse(), _BadJSONResponse()])
    browser = _AsyncBrowser(
        [
            json.dumps({"users": [{"username": "a"}], "next_max_id": "cursor"}),
            json.dumps({"users": [{"username": "b"}], "next_max_id": None}),
        ]
    )

    usernames = relationship_tools._get_relationship_usernames(
        browser, session, {}, "1", "followers", "full", _Logger()
    )

    assert usernames == ["a", "b"]
    assert browser.scripts[0][1][0] == (
        "/api/v1/friendships/1/followers/?count=50"
    )
    assert browser.scripts[1][1][0] == (
        "/api/v1/friendships/1/followers/?count=50&max_id=cursor"
    )


def test_relationship_usernames_discards_when_browser_also_fails(monkeypatch):
    monkeypatch.setattr(relationship_tools, "update_activity", _no_sleep)
    monkeypatch.setattr(relationship_tools, "sleep", _no_sleep)

    session = _Session([_BadJSONResponse()])
    browser = _AsyncBrowser(["<html>still blocked</html>"])
    logger = _Logger()

    usernames = relationship_tools._get_relationship_usernames(
        browser, session, {}, "1", "followers", "full", logger
    )

    assert usernames == []
    assert any("invalid JSON" in message for message in logger.messages)
    assert any("incomplete" in message for message in logger.messages)


def test_relationship_page_in_browser_returns_none_without_browser_support():
    logger = _Logger()

    assert (
        relationship_tools._get_relationship_page_in_browser(
            _Browser(), "1", "followers", None, logger
        )
        is None
    )
    assert any("In-browser" in message for message in logger.messages)
