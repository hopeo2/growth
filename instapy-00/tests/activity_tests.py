import unittest
from datetime import datetime, timedelta, timezone

from instapy.like_util import get_post_datetime


class ElementMock:
    def __init__(self, attributes):
        self.attributes = attributes

    def get_attribute(self, name):
        return self.attributes.get(name)

    def is_displayed(self):
        return True


class BrowserMock:
    def __init__(self, time_elements=None, meta_elements=None):
        self.time_elements = time_elements or []
        self.meta_elements = meta_elements or []

    def find_elements(self, by, xpath):
        if "time" in xpath:
            return list(self.time_elements)
        if "description" in xpath:
            return list(self.meta_elements)
        return []


class PostDatetimeTests(unittest.TestCase):
    def test_reads_iso_datetime_attribute(self):
        recent = datetime.now(timezone.utc) - timedelta(days=3)
        browser = BrowserMock(
            time_elements=[
                ElementMock(
                    {"datetime": recent.isoformat().replace("+00:00", "Z")}
                )
            ]
        )

        parsed = get_post_datetime(browser)

        self.assertIsNotNone(parsed)
        self.assertEqual((datetime.now(timezone.utc) - parsed).days, 3)

    def test_falls_back_to_meta_description(self):
        browser = BrowserMock(
            meta_elements=[
                ElementMock(
                    {
                        "content": (
                            '12 likes, 1 comments - someone on '
                            'July 18, 2026: "hello"'
                        )
                    }
                )
            ]
        )

        parsed = get_post_datetime(browser)

        self.assertEqual(parsed, datetime(2026, 7, 18, tzinfo=timezone.utc))

    def test_returns_none_when_date_is_missing(self):
        self.assertIsNone(get_post_datetime(BrowserMock()))


if __name__ == "__main__":
    unittest.main()
