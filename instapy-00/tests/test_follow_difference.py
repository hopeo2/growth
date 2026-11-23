"""Tests for the follower/following difference filter."""

from instapy.instapy import InstaPy
from instapy.util import validate_username


class _Logger:
    def __init__(self):
        self.messages = []

    def info(self, message):
        self.messages.append(("info", message))

    def warning(self, message):
        self.messages.append(("warning", message))

    def error(self, message):
        self.messages.append(("error", message))


def _validate(monkeypatch, counts, max_follow_difference, logfolder):
    monkeypatch.setattr(
        "instapy.util.get_relationship_counts",
        lambda browser, username, logger: counts,
    )

    return validate_username(
        browser=None,
        username_or_link="target",
        own_username="tester",
        ignore_users=[],
        blacklist={},
        potency_ratio=None,
        delimit_by_numbers=None,
        max_followers=None,
        max_following=None,
        min_followers=None,
        min_following=None,
        min_posts=None,
        max_posts=None,
        skip_private=False,
        skip_private_percentage=0,
        skip_public=False,
        skip_public_percentage=0,
        skip_no_profile_pic=False,
        skip_no_profile_pic_percentage=0,
        skip_business=False,
        skip_non_business=False,
        skip_business_percentage=0,
        skip_business_categories=[],
        dont_skip_business_categories=[],
        skip_bio_keyword=[],
        mandatory_bio_keywords=[],
        logger=_Logger(),
        logfolder=str(logfolder),
        max_follow_difference=max_follow_difference,
    )


def test_difference_within_limit_is_valid(monkeypatch, tmp_path):
    valid, _ = _validate(monkeypatch, (1000, 800), 300, tmp_path)
    assert valid is True


def test_difference_exactly_at_limit_is_valid(monkeypatch, tmp_path):
    valid, _ = _validate(monkeypatch, (1000, 700), 300, tmp_path)
    assert valid is True


def test_difference_above_limit_is_skipped(monkeypatch, tmp_path):
    valid, details = _validate(monkeypatch, (1000, 699), 300, tmp_path)
    assert valid is False
    assert "difference" in details


def test_difference_is_absolute(monkeypatch, tmp_path):
    valid, details = _validate(monkeypatch, (699, 1000), 300, tmp_path)
    assert valid is False
    assert "difference" in details


def test_check_is_optional(monkeypatch, tmp_path):
    valid, _ = _validate(monkeypatch, (10000, 1), None, tmp_path)
    assert valid is True


def test_zero_limit_is_enforced(monkeypatch, tmp_path):
    valid, _ = _validate(monkeypatch, (100, 100), 0, tmp_path)
    assert valid is True

    valid, _ = _validate(monkeypatch, (100, 101), 0, tmp_path)
    assert valid is False


def test_unknown_counts_do_not_block_user(monkeypatch, tmp_path):
    valid, _ = _validate(monkeypatch, (None, None), 300, tmp_path)
    assert valid is True


def test_relationship_bounds_accepts_max_follow_difference():
    session = InstaPy.__new__(InstaPy)

    session.set_relationship_bounds(enabled=True, max_follow_difference=300)
    assert session.max_follow_difference == 300

    session.set_relationship_bounds(enabled=True, max_follow_difference=None)
    assert session.max_follow_difference is None


def test_follow_difference_limit_defaults_to_300():
    session = InstaPy.__new__(InstaPy)

    session.set_follow_difference_limit()
    assert session.max_follow_difference == 300

    session.set_follow_difference_limit(enabled=False)
    assert session.max_follow_difference is None
