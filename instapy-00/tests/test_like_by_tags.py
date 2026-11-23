"""Tests for the per-tag skip / candidate handling in ``like_by_tags``."""

import pytest

from instapy.instapy import InstaPy


class _Logger:
    def __init__(self):
        self.messages = []

    def info(self, message):
        self.messages.append(("info", message))

    def warning(self, message):
        self.messages.append(("warning", message))

    def error(self, message):
        self.messages.append(("error", message))


def _make_session():
    session = InstaPy.__new__(InstaPy)
    session.aborting = False
    session.browser = None
    session.logger = _Logger()
    session.logfolder = None
    session.username = "tester"

    session.smart_hashtags = []
    session.smart_location_hashtags = []
    session.quotient_breach = False
    session.jumps = {"consequent": {"likes": 0}, "limit": {"likes": 100}}

    session.dont_like = []
    session.mandatory_words = []
    session.mandatory_language = False
    session.is_mandatory_character = False
    session.mandatory_character = None
    session.check_character_set = None
    session.ignore_if_contains = []
    session.max_post_age_days = 14
    session.blacklist = {"enabled": False}

    session.delimit_liking = False
    session.liking_approved = True
    session.do_comment_liked_photo = False
    session.use_clarifai = False

    session.do_comment = False
    session.comment_percentage = 0
    session.comments = []
    session.photo_comments = []
    session.video_comments = []
    session.dont_include = set()
    session.delimit_commenting = False
    session.max_comments = None
    session.min_comments = None
    session.comments_mandatory_words = []

    session.do_follow = False
    session.follow_percentage = 0
    session.follow_times = 1

    session.liked_img = 0
    session.already_liked = 0
    session.commented = 0
    session.followed = 0
    session.skipped_img = 0
    session.inap_img = 0
    session.not_valid_users = 0
    session.seen_post_links = set()

    return session


@pytest.fixture
def patched(monkeypatch):
    state = {
        "links": {},
        "checked": [],
        "old_links": set(),
    }

    def fake_get_links_for_tag(browser, tag, amount, *args, **kwargs):
        return list(state["links"].get(tag, []))

    def fake_check_link(browser, link, *args, **kwargs):
        state["checked"].append(link)
        if link in state["old_links"]:
            return True, "old_user", False, "Post is too old", "Inactive account"
        return False, "fresh_user", False, "None", "Success"

    def fake_validate_user_call(user_name):
        return True, "valid"

    def fake_like_image(*args, **kwargs):
        return True, "success"

    monkeypatch.setattr(
        "instapy.instapy.get_links_for_tag", fake_get_links_for_tag
    )
    monkeypatch.setattr("instapy.instapy.check_link", fake_check_link)
    monkeypatch.setattr(
        "instapy.instapy.web_address_navigator", lambda *a, **k: None
    )
    monkeypatch.setattr(
        InstaPy, "validate_user_call", lambda self, user: fake_validate_user_call(user)
    )
    monkeypatch.setattr("instapy.instapy.like_image", fake_like_image)

    return state


def test_stale_post_is_skipped_and_next_candidate_is_used(patched):
    session = _make_session()
    old = "https://www.instagram.com/p/OLD111/"
    fresh = "https://www.instagram.com/p/NEW222/"

    patched["links"] = {"tag": [old, fresh]}
    patched["old_links"] = {old}

    session.like_by_tags(["tag"], amount=2, max_posts_per_tag=1)

    assert patched["checked"] == [old, fresh]
    assert session.liked_img == 1
    assert session.skipped_img == 1
    assert session.inap_img == 0


def test_duplicate_post_is_not_visited_twice(patched):
    session = _make_session()
    post = "https://www.instagram.com/p/SAME333/"

    patched["links"] = {"tag_one": [post], "tag_two": [post]}

    session.like_by_tags(["tag_one", "tag_two"], amount=1, max_posts_per_tag=1)

    assert patched["checked"] == [post]
    assert session.liked_img == 1
