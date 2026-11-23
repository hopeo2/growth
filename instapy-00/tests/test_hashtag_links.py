"""Tests for hashtag link collection on the keyword-search layout."""

from instapy.like_util import get_links_for_tag


class _Logger:
    def info(self, message):
        pass

    def warning(self, message):
        pass

    def error(self, message):
        pass


class _FakeBrowser:
    """Keyword-search layout: empty at first, posts appear after scrolling."""

    def __init__(self, posts_after_scroll):
        self.current_url = (
            "https://www.instagram.com/explore/search/keyword/?q=%23test"
        )
        self.posts_after_scroll = posts_after_scroll
        self.collect_calls = 0
        self.scrolls = 0

    def execute_script(self, script, *args):
        if "querySelectorAll" in script:
            self.collect_calls += 1
            if self.collect_calls == 1:
                return []
            return self.posts_after_scroll
        if "scrollTo" in script:
            self.scrolls += 1
        return None

    def find_element(self, by, value):
        return object()

    def find_elements(self, by, value):
        return []


def _post(href):
    return {"href": href, "labels": [], "has_video": False}


def test_search_layout_scrolls_even_when_amount_is_one(monkeypatch):
    monkeypatch.setattr("instapy.like_util.sleep", lambda *a, **k: None)
    monkeypatch.setattr("instapy.like_util.update_activity", lambda *a, **k: None)
    monkeypatch.setattr(
        "instapy.like_util.web_address_navigator", lambda *a, **k: None
    )

    browser = _FakeBrowser(
        [
            _post("https://www.instagram.com/p/AAA/"),
            _post("https://www.instagram.com/p/BBB/"),
        ]
    )

    links = get_links_for_tag(
        browser, "test", 1, True, False, None, _Logger()
    )

    assert browser.scrolls > 0
    assert links == ["https://www.instagram.com/p/AAA/"]


class _FakeMainElement:
    def find_elements(self, by, value):
        return [object()]


class _FakeTagPageBrowser:
    """Classic hashtag page that already lists more posts than requested."""

    def __init__(self, post_count):
        self.current_url = "https://www.instagram.com/explore/tags/test/"
        self.posts = [
            _post("https://www.instagram.com/p/{}".format(index))
            for index in range(post_count)
        ]

    def execute_script(self, script, *args):
        if "querySelectorAll" in script:
            return self.posts
        return None

    def find_element(self, by, value):
        return _FakeMainElement()

    def find_elements(self, by, value):
        return []


def test_only_requested_amount_is_returned_after_removing_top_posts(monkeypatch):
    monkeypatch.setattr("instapy.like_util.sleep", lambda *a, **k: None)
    monkeypatch.setattr("instapy.like_util.update_activity", lambda *a, **k: None)
    monkeypatch.setattr(
        "instapy.like_util.web_address_navigator", lambda *a, **k: None
    )

    browser = _FakeTagPageBrowser(21)

    links = get_links_for_tag(browser, "test", 3, True, False, None, _Logger())

    # The first nine grid entries are top posts and must be dropped, but the
    # caller still only gets the three candidates it asked for.
    assert links == [post["href"] for post in browser.posts[9:12]]
