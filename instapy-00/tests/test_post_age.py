"""Tests for the post date / activity check helpers."""

from datetime import datetime, timezone

from instapy.like_util import (
    _caption_from_meta_description,
    _parse_meta_date,
    _post_shortcode,
    _unique_links,
    get_post_data_from_page,
    get_post_datetime,
)


class _FakeTimeouts:
    implicit_wait = 25


class _FakeElement:
    def __init__(self, **attributes):
        self.attributes = attributes

    def get_attribute(self, name):
        return self.attributes.get(name)


class _FakeBrowser:
    """Just enough of a WebDriver for the DOM based helpers."""

    def __init__(self, meta=None, times=()):
        self.timeouts = _FakeTimeouts()
        self.meta = meta
        self.times = list(times)

    def implicitly_wait(self, value):
        pass

    def find_elements(self, by, value):
        if "meta" in value:
            return [self.meta] if self.meta else []
        if "time" in value:
            return self.times
        return []


def test_parse_meta_date_handles_both_orders():
    assert _parse_meta_date(
        "209 likes, 1,563 comments - doostyabi60 on April 20, 2022"
    ) == datetime(2022, 4, 20, tzinfo=timezone.utc)

    assert _parse_meta_date("1,234 likes - someone on 9 November 2026") == datetime(
        2026, 11, 9, tzinfo=timezone.utc
    )

    assert _parse_meta_date("no date here") is None


def test_caption_is_extracted_from_meta_description():
    description = (
        '118 likes, 572 comments - r.verona1903 on July 2, 2026\u200e: "'
        "فالو کنید با افتخار بک می‌دم\"."
    )

    assert (
        _caption_from_meta_description(description)
        == "فالو کنید با افتخار بک می‌دم"
    )
    assert (
        _caption_from_meta_description(
            "209 likes, 1,563 comments - doostyabi60 on April 20, 2022"
        )
        is None
    )


def test_comment_timestamp_does_not_hide_old_post_date():
    """An old post with recent comments must not look like a fresh post."""
    browser = _FakeBrowser(
        meta=_FakeElement(
            content="209 likes, 1,563 comments - doostyabi60 on April 20, 2022"
        ),
        times=[
            _FakeElement(datetime="2026-11-19T10:00:00.000Z"),
            _FakeElement(datetime="2026-11-18T08:00:00.000Z"),
        ],
    )

    post_date = get_post_datetime(browser)

    assert post_date == datetime(2022, 4, 20, tzinfo=timezone.utc)
    assert (datetime.now(timezone.utc) - post_date).days > 14


def test_time_fallback_uses_the_earliest_timestamp():
    browser = _FakeBrowser(
        times=[
            _FakeElement(datetime="2026-11-19T10:00:00.000Z"),
            _FakeElement(datetime="2026-11-01T10:00:00.000Z"),
        ]
    )

    assert get_post_datetime(browser) == datetime(
        2026, 11, 1, 10, tzinfo=timezone.utc
    )


def test_post_data_uses_caption_not_the_whole_meta_description():
    browser = _FakeBrowser(
        meta=_FakeElement(
            content=(
                '57 likes, 182 comments - explorer_raftan on October 17, 2026'
                '\u200e: "کامنت بذار تا فالو کننت"'
            )
        )
    )

    user_name, caption, is_video = get_post_data_from_page(browser)

    assert user_name == "explorer_raftan"
    assert caption == "کامنت بذار تا فالو کننت"
    assert is_video is False


def test_post_shortcode_and_unique_links():
    assert _post_shortcode("https://www.instagram.com/p/DaS17KyopTS/") == (
        "DaS17KyopTS"
    )
    assert _post_shortcode("https://www.instagram.com/reel/ABC123/?x=1") == "ABC123"
    assert _post_shortcode("https://www.instagram.com/explore/tags/x/") is None

    assert _unique_links(["a", "b", "a", "c"]) == ["a", "b", "c"]
