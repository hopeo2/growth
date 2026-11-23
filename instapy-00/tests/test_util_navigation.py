"""Tests for the resilient web navigation helper."""

import urllib3
from selenium.common.exceptions import TimeoutException

import instapy.util as util


class _Browser:
    def __init__(self, get_errors=()):
        self.get_calls = []
        self.script_calls = []
        self._errors = list(get_errors)

    def get(self, link):
        self.get_calls.append(link)
        if self._errors:
            error = self._errors.pop(0)
            if error is not None:
                raise error

    def execute_script(self, script):
        self.script_calls.append(script)


class _Logger:
    def __init__(self):
        self.messages = []

    def warning(self, message):
        self.messages.append(message)


def _patch(monkeypatch, current_url="https://www.instagram.com"):
    monkeypatch.setattr(util, "get_current_url", lambda browser: current_url)
    monkeypatch.setattr(util, "update_activity", lambda *args, **kwargs: None)
    monkeypatch.setattr(util, "sleep", lambda *args, **kwargs: None)


def test_navigator_stops_and_survives_socket_timeout(monkeypatch):
    _patch(monkeypatch)
    timeout = urllib3.exceptions.ReadTimeoutError(None, "/", "timed out")
    browser = _Browser(get_errors=[timeout, timeout])
    logger = _Logger()

    util.web_address_navigator(
        browser, "https://www.instagram.com/p/abc", logger
    )

    assert len(browser.get_calls) == 2
    assert "window.stop();" in browser.script_calls
    assert any("Failed to load" in message for message in logger.messages)


def test_navigator_survives_selenium_timeout(monkeypatch):
    _patch(monkeypatch)
    browser = _Browser(
        get_errors=[TimeoutException("page load timed out")] * 2
    )

    util.web_address_navigator(browser, "https://www.instagram.com/p/xyz")

    assert len(browser.get_calls) == 2


def test_navigator_navigates_when_url_differs(monkeypatch):
    _patch(monkeypatch)
    browser = _Browser()

    util.web_address_navigator(browser, "https://www.instagram.com/p/abc")

    assert browser.get_calls == ["https://www.instagram.com/p/abc"]


def test_navigator_skips_when_already_on_page(monkeypatch):
    _patch(monkeypatch, current_url="https://www.instagram.com/p/abc")
    browser = _Browser()

    util.web_address_navigator(browser, "https://www.instagram.com/p/abc")

    assert browser.get_calls == []
