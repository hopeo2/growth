"""Tests for the unfollow helpers."""

import instapy.unfollow_util as unfollow_util


def test_confirm_unfollow_clicks_visible_role_button(monkeypatch):
    clicked = []

    class _Element:
        text = "Unfollow"

        def is_displayed(self):
            return True

        def get_attribute(self, name):
            return ""

    class _Browser:
        def find_elements(self, by, xpath):
            return [_Element()]

    monkeypatch.setattr(
        unfollow_util,
        "click_element",
        lambda browser, element: clicked.append(element),
    )
    monkeypatch.setattr(unfollow_util, "sleep", lambda *args, **kwargs: None)

    unfollow_util.confirm_unfollow(_Browser())

    assert len(clicked) == 1
    assert clicked[0].text == "Unfollow"


def test_confirm_unfollow_ignores_hidden_candidates(monkeypatch):
    clicked = []

    class _Element:
        text = "Unfollow"

        def is_displayed(self):
            return False

        def get_attribute(self, name):
            return ""

    class _Browser:
        def find_elements(self, by, xpath):
            return [_Element()]

    monkeypatch.setattr(
        unfollow_util,
        "click_element",
        lambda browser, element: clicked.append(element),
    )
    monkeypatch.setattr(unfollow_util, "sleep", lambda *args, **kwargs: None)

    unfollow_util.confirm_unfollow(_Browser())

    assert clicked == []