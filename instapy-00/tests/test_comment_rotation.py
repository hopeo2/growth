"""Tests for the no-repeat comment rotation used by the comment engine."""

import instapy.comment_util as comment_util
from instapy.comment_util import choose_comment


def _reset():
    comment_util._comment_decks.clear()
    comment_util._last_comments.clear()


def test_choose_comment_uses_every_comment_once_per_cycle():
    _reset()
    comments = ["a", "b", "c", "d", "e"]

    first_cycle = [choose_comment(comments) for _ in range(len(comments))]
    second_cycle = [choose_comment(comments) for _ in range(len(comments))]

    assert sorted(first_cycle) == sorted(comments)
    assert sorted(second_cycle) == sorted(comments)


def test_choose_comment_does_not_repeat_across_cycle_boundary():
    _reset()
    comments = ["a", "b", "c"]

    chosen = [choose_comment(comments) for _ in range(len(comments) * 3)]

    for before, after in zip(chosen, chosen[1:]):
        assert before != after, chosen


def test_choose_comment_handles_empty_and_single_lists():
    _reset()

    assert choose_comment([]) == ""
    assert choose_comment(["only"]) == "only"
    assert choose_comment(["only"]) == "only"