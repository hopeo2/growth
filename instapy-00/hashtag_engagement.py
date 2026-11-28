#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Follow, like and comment on posts that use the configured hashtags.

Safety features (enabled by default):

  * low action rates and long, randomized pauses,
  * hourly and daily caps for likes, comments, follows and unfollows,
  * a cooldown between runs,
  * a lock that prevents two runs from using the same account at once,
  * a hard time limit for each run,
  * a follow filter that only follows accounts whose follower and following
    counts differ by at most 5000 (it never blocks likes or comments),
  * unfollows accounts that have not followed back within 3 days and keeps
    them on a permanent "do not follow" list,
  * a check of today's recorded usage before and during the run.

For every post found under the given hashtags InstaPy will like the post,
post one Persian comment and follow the author of the post (only once per
author). Only posts published in the last week are used, so accounts that
have gone inactive are skipped. Comments are taken from a shuffled "deck" and
are not repeated until every comment has been used once. Authors that have not
followed back within 3 days are unfollowed and are never followed again.

The work is split into independent tasks so any one of them can be run on its
own: hashtags, unfollow, comments (like/reply on comments) and stories. Run the
script in a terminal with no task flags and it asks which tasks to run and then
about the remaining options, showing the current default for each so Enter keeps
it. Pass ``--no-interactive`` (or use a cron/script) to skip the questions; then
no task flag means every task runs, and ``--all-tasks`` also runs everything.

After the hashtag loop the script also engages with the accounts it already
follows: it watches their stories, likes comments on their recent posts and
replies to a percentage of those comments. These extra actions stay small and
are still limited by the same hourly and daily caps.

Credentials are read from ``INSTA_USER`` / ``INSTA_PW`` or from
``--username`` / ``--password``. After the first successful login InstaPy
stores the session cookie in the workspace and later runs reuse it, so no
password is needed again while the session remains valid.

Examples
--------
Preview the configuration without opening a browser::

    venv/bin/python hashtag_engagement.py --dry-run

First run (logs in and saves the session)::

    INSTA_USER="your_username" INSTA_PW="your_password" \
        venv/bin/python hashtag_engagement.py

Later runs (reuse the saved session, no password)::

    INSTA_USER="your_username" venv/bin/python hashtag_engagement.py

Use your own hashtags/comments and hide the browser window::

    venv/bin/python hashtag_engagement.py \
        --tags-file my_hashtags.txt \
        --comments-file my_comments.txt \
        --replies-file my_replies.txt \
        --headless

Turn off the extra engagement features (comment likes, replies, stories)::

    venv/bin/python hashtag_engagement.py \
        --like-comments-accounts 0 \
        --reply-percentage 0 \
        --story-accounts 0

Run a single task on its own (useful between full runs)::

    venv/bin/python hashtag_engagement.py --unfollow
    venv/bin/python hashtag_engagement.py --hashtags
    venv/bin/python hashtag_engagement.py --comments
    venv/bin/python hashtag_engagement.py --stories

Run every task together (this is also the default when no task flag is
given)::

    venv/bin/python hashtag_engagement.py --all-tasks

Run without flags and answer the questions instead (Enter keeps each default)::

    venv/bin/python hashtag_engagement.py

Skip the questions, for example in a cron job::

    venv/bin/python hashtag_engagement.py --no-interactive

No automation can guarantee that an Instagram account will never be blocked.
These controls make the activity slow and bounded, but they do not make it
risk-free. Use an account you can afford to lose.
"""

import argparse
import csv
import json
import os
import random
import re
import sqlite3
import sys
import time
from datetime import datetime
from urllib.parse import quote

from instapy import InstaPy, get_workspace, set_workspace, smart_run
from instapy.settings import Settings
from instapy.unfollow_util import follow_restriction

# ---------------------------------------------------------------------------
# Default targets
# ---------------------------------------------------------------------------

# Hashtags are grouped so it is easy to see why a tag is in the list. The bot
# rotates through the whole list across runs. Popular and trending tags are
# mixed with the mutual-support tags the account already targets, so the page
# can be discovered by a wider audience without losing the follow-for-follow
# niche.
DEFAULT_HASHTAGS = [
    # Persian follow / like / comment exchanges
    "فالو_متقابل",
    "حمایت_متقابل",
    "تبادل_فالو",
    "تبادل_لایک",
    "تبادل_کامنت",
    "فالو_بک",
    "فالوبک",
    "لایک_متقابل",
    "کامنت_متقابل",
    "حمایت_واقعی",
    "معرفی_پیج",
    "لایک_فالو",
    "فالو_و_لایک",
    "تبادل",
    "حمایت",
    "فالو_کن",
    "فالو_میکنم",
    "فالو_میشی",
    "فالو",
    "لایک",
    "کامنت",
    "رشد_اینستاگرام",
    "حمایت_از_مشاغل_خانگی",
    # Persian growth and discovery
    "اینستاگرام",
    "پیج_من",
    "رشد_پیج",
    "فالو_بک_فوری",
    "حمایت_کن",
    "کامنت_کن",
    "لایک_کن",
    "تبادل_فالو_و_لایک",
    # Popular Persian content and lifestyle tags
    "ایران",
    "تهران",
    "عکس",
    "مد",
    "زیبایی",
    "ورزش",
    "غذا",
    "سفر",
    "طبیعت",
    "هنر",
    "موسیقی",
    "کتاب",
    "انگیزه",
    "موفقیت",
    "کسب_و_کار",
    "کارآفرینی",
    # Globally popular / trending tags
    "followforfollow",
    "likeforlike",
    "instagood",
    "photooftheday",
    "explorepage",
    "fyp",
    "viral",
    "reels",
]

# A large, varied list is the first line of defence against repetitive
# comments. ``instapy.comment_util.choose_comment`` then cycles through a
# shuffled "deck", so every comment is used once before any comment is
# repeated.
DEFAULT_COMMENTS = [
    # Compliments
    "عالی بود 👌",
    "چقدر قشنگ ❤️",
    "بینظیر 🔥",
    "دمت گرم 👏",
    "واقعاً جذاب بود",
    "چه سلیقهای 😍",
    "محشره 👌",
    "حرف نداشت 🔥",
    "همیشه بدرخشی 🌟",
    "خیلی خفن بود 👏",
    "این یکی متفاوت بود ✨",
    "چقدر دوستداشتنی ❤️",
    "عالی مثل همیشه 👌",
    "فوقالعاده 👏",
    "پر از حس خوب 🌷",
    "ترکوندی 😍",
    "واقعاً دیدنی بود ✨",
    "چه عکس قشنگی 📸",
    "سلیقه یعنی این 😍",
    "منتظر پست بعدی هستیم ⏳",
    "چقدر حرفهای 👏",
    "این خیلی جالب بود ✨",
    "بهترین 👌",
    "در یک کلام عالی ❤️",
    "چه انرژی خوبی 🌞",
    "واقعاً تحسینبرانگیزه 👏",
    "ممنون بابت اشتراکگذاری 🙏",
    "این پست ارزش دیدن داشت ❤️",
    "همینطور ادامه بده 💪",
    "پایدار و موفق باشی 🌟",
    # Questions that invite a reply
    "نظرت درباره پست بعدی چیه؟ 🤔",
    "این عکس کجا گرفته شده؟ 📍",
    "چقدر خوب بود، موافقی؟ 😊",
    "این ایده رو از کجا آوردی؟ ✨",
    "چه رنگهایی، عالیه نه؟ 🎨",
    "دوست داری پست بعدی درباره چی باشه؟ 💬",
    "این یکی رو دوست داشتی؟ ❤️",
    "کی منتظر پست بعدیشه؟ 🙋",
    "این سبک رو ادامه بده؟ 👏",
    "نظرت چیه؟ 💭",
    # Mutual support / growth
    "فالو کردم، خوشحال میشم متقابل حمایت کنی ❤️",
    "فالو دوطرفه؟ 🌹",
    "من حمایت کردم، نوبت شماست 😍",
    "پایه حمایت متقابل هستی؟ 🤝",
    "فالو بک یادت نره ❤️",
    "بیایید از هم حمایت کنیم 🤝",
    "حمایت کنیم تا همه رشد کنیم 🌱",
    "من همراهتم، تو هم همراه باش ❤️",
    "فالو کردم، منتظر حمایتت هستم 🌹",
    "دوستان فعال همدیگه رو حمایت کنیم ❤️",
    "لایک و کامنت متقابل، بیا جلو 🚀",
    "حمایتت میکنم، حمایتم کن 🙏",
    "با هم رشد کنیم 🌿",
    "پیجت ارزش حمایت داره ❤️",
    # Short reactions
    "فوقالعاده بود 🔥",
    "عالی 👏",
    "دوستش داشتم 😍",
    "خیلی خوب 👌",
    "زیبا ❤️",
    "آفرین 🌟",
    "چه انرژیای 💪",
    "خوشم آمد 😊",
    "بینظیر بود ✨",
    "ادامه بده 🚀",
    # Encouragement
    "ادامه بده، داری عالی پیش میری 💪",
    "موفقیت نزدیکه 🌟",
    "الهامبخش بود 🙏",
    "پر از انگیزه ❤️",
    "این محتوا حال آدمو خوب میکنه 🌞",
    "ارزش دیدن داشت 👌",
    "خسته نباشی 🙏",
    "پررونق باشی 🌷",
]

# Replies posted under comments when comment engagement is enabled. InstaPy
# mentions the commenter automatically (``@username <reply>``). Replies count
# toward the same comment caps as normal comments.
DEFAULT_REPLIES = [
    "ممنون از حمایتت ❤️",
    "لطف داری 🙏",
    "خیلی هم عالی 👌",
    "ممنون که همراهی 🌹",
    "قربونت، موفق باشی 🌟",
    "چه کامنت قشنگی 😍",
    "دمت گرم 🙏",
    "همراهت هستیم 💚",
    "مرسی از انرژی خوبت 🌞",
    "لایک داری از ما ❤️",
    "ممنون از توجهت ✨",
    "ارادتمند 🙏",
]

STATE_FILENAME = "engagement_state.json"
LOCK_FILENAME = "engagement.lock"
# The follower/following difference limit only decides whether an account is
# followed; likes and comments are never limited by it. Persian
# follow-for-follow communities are full of accounts with a lopsided ratio,
# and a 300 difference blocked almost every action, so the default is now much
# more permissive (set it to 0 to disable the follow check entirely).
DEFAULT_MAX_FOLLOW_DIFFERENCE = 5000
DEFAULT_UNFOLLOW_AFTER_DAYS = 3
# Only posts published in the last week are used, so the bot interacts only
# with accounts that are still active.
DEFAULT_MAX_POST_AGE_DAYS = 7

# Independent tasks. Each one can be selected on its own with the matching
# command-line flag, or all of them together with ``--all-tasks``.
TASK_HASHTAGS = "hashtags"
TASK_UNFOLLOW = "unfollow"
TASK_COMMENTS = "comments"
TASK_STORIES = "stories"
ALL_TASKS = (TASK_HASHTAGS, TASK_UNFOLLOW, TASK_COMMENTS, TASK_STORIES)
TASK_DESCRIPTIONS = {
    TASK_HASHTAGS: "like, comment on and follow posts under the hashtags",
    TASK_UNFOLLOW: "unfollow accounts that did not follow back in time",
    TASK_COMMENTS: "like comments on followed accounts and reply to some",
    TASK_STORIES: "watch stories of followed accounts",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def selected_tasks(args):
    """Return the set of tasks requested on the command line.

    If no task flag is given, or ``--all-tasks`` is used, every task is
    returned. That keeps the original behaviour (do everything) as the
    default, while the individual flags let a run do only one job.
    """
    if getattr(args, "task_all", False):
        return set(ALL_TASKS)

    chosen = set()
    for task, attribute in (
        (TASK_HASHTAGS, "task_hashtags"),
        (TASK_UNFOLLOW, "task_unfollow"),
        (TASK_COMMENTS, "task_comments"),
        (TASK_STORIES, "task_stories"),
    ):
        if getattr(args, attribute, False):
            chosen.add(task)

    return chosen or set(ALL_TASKS)


def _read_answer(prompt, default_text):
    """Read one line, treating an empty answer as the default."""
    try:
        return input("{} [{}]: ".format(prompt, default_text)).strip()
    except EOFError:
        print()
        return ""
    except KeyboardInterrupt:
        print()
        sys.exit("Cancelled.")


def ask_int(prompt, default):
    """Ask for a whole number; Enter keeps the current value."""
    while True:
        raw = _read_answer(prompt, default)
        if raw == "":
            return default
        try:
            return int(raw)
        except ValueError:
            print("  Please enter a whole number (or press Enter for {}).".format(default))


def ask_float(prompt, default):
    """Ask for a decimal number; Enter keeps the current value."""
    while True:
        raw = _read_answer(prompt, default)
        if raw == "":
            return default
        try:
            return float(raw)
        except ValueError:
            print("  Please enter a number (or press Enter for {}).".format(default))


def ask_bool(prompt, default):
    """Ask a yes/no question; Enter keeps the current value."""
    default_text = "Y/n" if default else "y/N"
    raw = _read_answer(prompt, default_text).lower()
    if raw == "":
        return default
    return raw in ("y", "yes", "1", "true")


def ask_text(prompt, default):
    """Ask for a free-text value; Enter keeps the current value."""
    default_text = default if default else "keep current"
    raw = _read_answer(prompt, default_text)
    if raw == "":
        return default
    if raw.lower() in ("none", "null", "-"):
        return None
    return raw


def ask_tasks(default_tasks):
    """Show a numbered menu and return the set of tasks to run."""
    print()
    print("What should this run do?")
    for index, task in enumerate(ALL_TASKS, 1):
        print("  {}. {} - {}".format(index, task, TASK_DESCRIPTIONS[task]))
    print("  0. every task")

    while True:
        raw = _read_answer("Choose tasks (e.g. 1,3 or 0 for all)", "all").lower()
        if raw in ("", "all", "0", "*", "a"):
            return set(ALL_TASKS)

        chosen = set()
        for part in re.split(r"[,\s]+", raw):
            if part.isdigit():
                number = int(part)
                if 1 <= number <= len(ALL_TASKS):
                    chosen.add(ALL_TASKS[number - 1])
        if chosen:
            return chosen
        print("  Please pick task numbers such as 1, 3 or 0 for all.")


def run_interactive(args):
    """Ask the user what to run and how, showing the current default each time.

    Every question can be skipped with Enter, and each setting is validated
    afterwards by ``validate_args`` exactly like a command-line flag.
    """
    print("=" * 62)
    print("Interactive setup - press Enter to keep the value in brackets.")
    print("=" * 62)

    args.tasks = ask_tasks(args.tasks)
    tasks = args.tasks

    if TASK_HASHTAGS in tasks:
        print("\nHashtag task:")
        args.amount = ask_int(
            "  Posts to process per hashtag", args.amount
        )
        args.candidates_per_hashtag = ask_int(
            "  Candidate posts inspected per hashtag",
            args.candidates_per_hashtag,
        )
        args.follow_percentage = ask_int(
            "  Follow percentage", args.follow_percentage
        )
        args.comment_percentage = ask_int(
            "  Comment percentage", args.comment_percentage
        )
        args.max_follow_difference = ask_int(
            "  Max follower/following difference (0 disables)",
            args.max_follow_difference,
        )
        args.include_top_posts = ask_bool(
            "  Also interact with the hashtag top posts?",
            args.include_top_posts,
        )
        args.tags_file = ask_text(
            "  Hashtags file (Enter = built-in list)", args.tags_file
        )
        args.comments_file = ask_text(
            "  Comments file (Enter = built-in list)", args.comments_file
        )
        args.replies_file = ask_text(
            "  Replies file (Enter = built-in list)", args.replies_file
        )

    if TASK_COMMENTS in tasks:
        print("\nComment engagement task:")
        args.like_comments_accounts = ask_int(
            "  Followed accounts to use (0 disables)",
            args.like_comments_accounts,
        )
        args.like_comments_posts = ask_int(
            "  Posts inspected per account", args.like_comments_posts
        )
        args.like_comments_per_post = ask_int(
            "  Comments liked per post", args.like_comments_per_post
        )
        args.reply_percentage = ask_int(
            "  Reply percentage (0 disables replies)", args.reply_percentage
        )

    if TASK_STORIES in tasks:
        print("\nStory task:")
        args.story_accounts = ask_int(
            "  Followed accounts whose stories are watched (0 disables)",
            args.story_accounts,
        )

    if TASK_UNFOLLOW in tasks:
        print("\nUnfollow task:")
        args.unfollow_after_days = ask_int(
            "  Days to wait for a follow back (0 disables)",
            args.unfollow_after_days,
        )

    print("\nSafety limits:")
    args.max_post_age_days = ask_int(
        "  Only interact with posts from the last N days (0 disables)",
        args.max_post_age_days,
    )
    args.max_likes_hourly = ask_int(
        "  Hourly like cap", args.max_likes_hourly
    )
    args.max_likes_daily = ask_int("  Daily like cap", args.max_likes_daily)
    args.max_comments_hourly = ask_int(
        "  Hourly comment cap", args.max_comments_hourly
    )
    args.max_comments_daily = ask_int(
        "  Daily comment cap", args.max_comments_daily
    )
    args.max_follows_hourly = ask_int(
        "  Hourly follow cap", args.max_follows_hourly
    )
    args.max_follows_daily = ask_int(
        "  Daily follow cap", args.max_follows_daily
    )
    args.max_unfollows_hourly = ask_int(
        "  Hourly unfollow cap", args.max_unfollows_hourly
    )
    args.max_unfollows_daily = ask_int(
        "  Daily unfollow cap", args.max_unfollows_daily
    )

    print("\nPacing and limits:")
    args.max_run_minutes = ask_int(
        "  Maximum run time in minutes", args.max_run_minutes
    )
    args.min_hours_between_runs = ask_float(
        "  Cooldown between runs in hours", args.min_hours_between_runs
    )
    args.chunk_size = ask_int(
        "  Hashtags before a long pause", args.chunk_size
    )
    args.chunk_pause_min = ask_float(
        "  Minimum long pause in minutes", args.chunk_pause_min
    )
    args.chunk_pause_max = ask_float(
        "  Maximum long pause in minutes", args.chunk_pause_max
    )

    print("\nBrowser:")
    args.headless = ask_bool(
        "  Run Firefox headless (no visible window)?", args.headless
    )

    print()
    return args


def should_prompt(args):
    """Return True when the interactive setup should run.

    Prompts appear only for a real terminal, never for ``--dry-run``, a
    ``--no-interactive`` run (cron/scripts) or a run that already picked
    tasks with flags.
    """
    if getattr(args, "no_interactive", False):
        return False
    if args.dry_run:
        return False
    if getattr(args, "tasks_explicit", False):
        return False

    readable = hasattr(sys.stdin, "isatty") and sys.stdin.isatty()
    writable = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    return readable and writable


def parse_args():
    """Parse this script's flags, leaving InstaPy's own flags untouched."""
    parser = argparse.ArgumentParser(
        description=(
            "Follow, like and comment on Instagram posts that use the "
            "configured hashtags. Safety limits are always enabled."
        )
    )

    parser.add_argument("-u", "--username", help="Instagram username")
    parser.add_argument(
        "-p",
        "--password",
        help="Instagram password (prefer the INSTA_PW environment variable)",
    )
    parser.add_argument(
        "--amount",
        type=int,
        default=1,
        help="posts to interact with per hashtag (default: 1)",
    )
    parser.add_argument(
        "--candidates-per-hashtag",
        type=int,
        default=5,
        help=(
            "candidate posts to inspect per hashtag so stale or unavailable "
            "posts do not waste the hashtag (default: 5)"
        ),
    )
    parser.add_argument(
        "--tags-file",
        help="text file with one hashtag per line (replaces the built-in list)",
    )
    parser.add_argument(
        "--comments-file",
        help="text file with one comment per line (replaces the built-in list)",
    )
    parser.add_argument(
        "--follow-percentage",
        type=int,
        default=80,
        help="percentage of processed posts whose author is followed (default: 80)",
    )
    parser.add_argument(
        "--max-follow-difference",
        type=int,
        default=DEFAULT_MAX_FOLLOW_DIFFERENCE,
        help=(
            "only follow accounts whose follower and following counts differ "
            "by at most this amount; likes and comments are never limited by "
            "it (default: {}; 0 disables the follow check)".format(
                DEFAULT_MAX_FOLLOW_DIFFERENCE
            )
        ),
    )
    parser.add_argument(
        "--comment-percentage",
        type=int,
        default=50,
        help="percentage of processed posts that get a comment (default: 50)",
    )
    parser.add_argument(
        "--replies-file",
        help="text file with one reply per line (replaces built-in replies)",
    )
    parser.add_argument(
        "--reply-percentage",
        type=int,
        default=30,
        help=(
            "percentage of liked comments that get a reply during comment "
            "engagement (default: 30; 0 disables replies)"
        ),
    )
    parser.add_argument(
        "--like-comments-accounts",
        type=int,
        default=3,
        help=(
            "followed accounts whose posts are used to like comments and "
            "reply (default: 3; 0 disables comment engagement)"
        ),
    )
    parser.add_argument(
        "--like-comments-posts",
        type=int,
        default=1,
        help=(
            "recent posts inspected per account for comment engagement "
            "(default: 1)"
        ),
    )
    parser.add_argument(
        "--like-comments-per-post",
        type=int,
        default=2,
        help=(
            "comments liked per post during comment engagement (default: 2)"
        ),
    )
    parser.add_argument(
        "--story-accounts",
        type=int,
        default=5,
        help=(
            "followed accounts whose stories are watched each run "
            "(default: 5; 0 disables story watching)"
        ),
    )
    parser.add_argument(
        "--max-likes-hourly",
        type=int,
        default=25,
        help="hourly like cap (default: 25)",
    )
    parser.add_argument(
        "--max-likes-daily",
        type=int,
        default=80,
        help="daily like cap (default: 80)",
    )
    parser.add_argument(
        "--max-comments-hourly",
        type=int,
        default=5,
        help="hourly comment cap (default: 5)",
    )
    parser.add_argument(
        "--max-comments-daily",
        type=int,
        default=15,
        help="daily comment cap (default: 15)",
    )
    parser.add_argument(
        "--max-follows-hourly",
        type=int,
        default=10,
        help="hourly follow cap (default: 10)",
    )
    parser.add_argument(
        "--max-follows-daily",
        type=int,
        default=30,
        help="daily follow cap (default: 30)",
    )
    parser.add_argument(
        "--unfollow-after-days",
        type=int,
        default=DEFAULT_UNFOLLOW_AFTER_DAYS,
        help=(
            "unfollow accounts that have not followed back within this many "
            "days and never follow them again (default: 3; 0 disables)"
        ),
    )
    parser.add_argument(
        "--max-unfollows-hourly",
        type=int,
        default=10,
        help="hourly unfollow cap (default: 10)",
    )
    parser.add_argument(
        "--max-unfollows-daily",
        type=int,
        default=30,
        help="daily unfollow cap (default: 30)",
    )
    parser.add_argument(
        "--max-run-minutes",
        type=int,
        default=45,
        help="hard time limit for one run in minutes (default: 45)",
    )
    parser.add_argument(
        "--max-post-age-days",
        type=int,
        default=DEFAULT_MAX_POST_AGE_DAYS,
        help=(
            "only interact with posts published within this many days, so "
            "inactive accounts are skipped (default: {}; 0 disables)"
            .format(DEFAULT_MAX_POST_AGE_DAYS)
        ),
    )
    parser.add_argument(
        "--min-hours-between-runs",
        type=float,
        default=3.0,
        help="cooldown before another run may start (default: 3 hours)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=4,
        help="number of hashtags processed before a long pause (default: 4)",
    )
    parser.add_argument(
        "--chunk-pause-min",
        type=float,
        default=2.0,
        help="minimum pause between hashtag groups in minutes (default: 2)",
    )
    parser.add_argument(
        "--chunk-pause-max",
        type=float,
        default=4.0,
        help="maximum pause between hashtag groups in minutes (default: 4)",
    )
    parser.add_argument(
        "--include-top-posts",
        action="store_true",
        help="also interact with the hashtag's top posts (skipped by default)",
    )
    parser.add_argument(
        "--headless",
        "--headless-browser",
        dest="headless",
        action="store_true",
        help="run Firefox without a visible window",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the configuration and exit without opening a browser",
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help=(
            "never ask questions; use only the flags and defaults "
            "(useful for cron and scripted runs)"
        ),
    )

    task_group = parser.add_argument_group(
        "tasks",
        "Choose one or more tasks. With no task flag (or with --all-tasks) "
        "every task runs, which is the default behaviour.",
    )
    task_group.add_argument(
        "--hashtags",
        dest="task_hashtags",
        action="store_true",
        help="run the hashtag task: like, comment on and follow posts",
    )
    task_group.add_argument(
        "--unfollow",
        dest="task_unfollow",
        action="store_true",
        help=(
            "run the unfollow task: unfollow accounts that have not followed "
            "back within --unfollow-after-days (default: 3)"
        ),
    )
    task_group.add_argument(
        "--comments",
        dest="task_comments",
        action="store_true",
        help=(
            "run the comment task: like comments on followed accounts' "
            "recent posts and reply to some"
        ),
    )
    task_group.add_argument(
        "--stories",
        dest="task_stories",
        action="store_true",
        help="run the story task: watch stories of followed accounts",
    )
    task_group.add_argument(
        "--all-tasks",
        dest="task_all",
        action="store_true",
        help="run every task together (default when no task flag is given)",
    )

    # InstaPy reads its own flags from sys.argv as well, so ignore anything
    # this parser does not know instead of raising an error.
    args, _ = parser.parse_known_args()
    args.tasks = selected_tasks(args)
    args.tasks_explicit = bool(
        args.task_all
        or args.task_hashtags
        or args.task_unfollow
        or args.task_comments
        or args.task_stories
    )
    return args


def read_lines(path):
    """Return non-empty, non-comment lines from a UTF-8 text file."""
    with open(path, "r", encoding="utf-8") as file_handle:
        lines = []
        for line in file_handle:
            line = line.strip()
            if line and not line.startswith("//"):
                lines.append(line)
        return lines


def collect_hashtags(values):
    """Split, clean and de-duplicate hashtags while preserving order."""
    hashtags = []
    for value in values:
        for part in re.split(r"[\s,،;؛]+", value):
            tag = part.strip().lstrip("#").strip()
            if tag and tag not in hashtags:
                hashtags.append(tag)
    return hashtags


def collect_comments(values):
    """Clean and de-duplicate comments while preserving order."""
    comments = []
    for value in values:
        for line in value.splitlines():
            comment = line.strip()
            if comment and comment not in comments:
                comments.append(comment)
    return comments


def clamp_percentage(value):
    return max(0, min(100, value))


def load_state(path):
    """Read the small JSON state file, returning an empty dict on errors."""
    try:
        with open(path, "r", encoding="utf-8") as file_handle:
            data = json.load(file_handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(path, state):
    """Write the state file atomically."""
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as file_handle:
        json.dump(state, file_handle, indent=2)
    os.replace(temporary, path)


def _parse_state_time(value):
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def check_run_gap(state, minimum_hours, tasks=None):
    """Return True when every task to run is past its own cooldown.

    Each task keeps its own last-run time, so running ``--unfollow`` is not
    blocked by a hashtag run that happened ten minutes earlier. Old state
    files that only contain ``last_run`` are still honoured until the next
    run writes the per-task times.
    """
    if minimum_hours <= 0:
        return True

    tasks = set(tasks) if tasks else set(ALL_TASKS)
    last_runs = state.get("last_run_by_task")
    if not isinstance(last_runs, dict):
        last_runs = {}

    # Only use the old global timestamp when no per-task data exists yet.
    use_legacy = not last_runs
    legacy_run = _parse_state_time(state.get("last_run")) if use_legacy else None
    now = datetime.now()
    blocking = []
    longest_wait = 0.0

    for task in tasks:
        last_time = _parse_state_time(last_runs.get(task))
        if last_time is None and use_legacy:
            last_time = legacy_run
        if last_time is None:
            continue

        elapsed_hours = (now - last_time).total_seconds() / 3600
        if elapsed_hours < minimum_hours:
            blocking.append(task)
            longest_wait = max(
                longest_wait, (minimum_hours - elapsed_hours) * 60
            )

    if not blocking:
        return True

    print(
        "Cooldown active for {}: the last run was too recent. "
        "Wait about {:.0f} more minute(s).".format(
            ", ".join(sorted(blocking)), longest_wait
        )
    )
    return False


def acquire_lock(path, stale_minutes):
    """Create a lock file. Return False when another run owns it."""
    if os.path.exists(path):
        age_minutes = (time.time() - os.path.getmtime(path)) / 60
        if age_minutes < stale_minutes:
            return False
        try:
            os.remove(path)
        except OSError:
            return False

    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False

    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
    finally:
        os.close(descriptor)

    return True


def release_lock(path):
    try:
        os.remove(path)
    except OSError:
        pass


def saved_session_path(username, workspace_path):
    """Path of the cookie InstaPy stores for an account."""
    return os.path.join(
        workspace_path, "logs", username, "{}_cookie.pkl".format(username)
    )


def followed_pool_usernames(logfolder, username):
    """Return the usernames currently stored in InstaPy's followed pool."""
    path = os.path.join(logfolder, "{}_followedPool.csv".format(username))
    usernames = set()

    try:
        with open(path, "r", encoding="utf-8") as file_handle:
            for row in csv.reader(file_handle):
                if not row:
                    continue
                entries = row[0].split(" ~ ")
                if len(entries) >= 2:
                    usernames.add(entries[1])
                elif entries[0]:
                    usernames.add(entries[0])
    except OSError:
        pass

    return usernames


def build_run_order(hashtags, state):
    """Return the saved hashtag cycle and the next position to process.

    Shuffling is done once per full cycle and stored, so a run that hits the
    time limit continues with the remaining hashtags next time instead of
    starting over from a random point.
    """
    stored = state.get("hashtag_order")

    if (
        isinstance(stored, list)
        and len(stored) == len(hashtags)
        and set(stored) == set(hashtags)
    ):
        order = stored
    else:
        order = list(hashtags)
        random.shuffle(order)
        state["hashtag_order"] = order
        state["hashtag_position"] = 0

    position = state.get("hashtag_position", 0)
    if not isinstance(position, int) or not 0 <= position < len(order):
        position = 0

    return order, position


def today_usage(username):
    """Read the account's action counts for the current local day."""
    usage = {"likes": 0, "comments": 0, "follows": 0, "unfollows": 0}
    database = Settings.database_location

    if not database or not os.path.isfile(database):
        return usage

    try:
        connection = sqlite3.connect(database)
        try:
            with connection:
                row = connection.execute(
                    "SELECT COALESCE(SUM(r.likes), 0), "
                    "COALESCE(SUM(r.comments), 0), "
                    "COALESCE(SUM(r.follows), 0), "
                    "COALESCE(SUM(r.unfollows), 0) "
                    "FROM recordActivity r "
                    "JOIN profiles p ON p.id = r.profile_id "
                    "WHERE p.name = ? AND "
                    "STRFTIME('%Y-%m-%d', r.created) = "
                    "STRFTIME('%Y-%m-%d', 'now', 'localtime')",
                    (username,),
                ).fetchone()
        finally:
            connection.close()
    except sqlite3.Error as error:
        print("Could not read today's usage: {}".format(error))
        return usage

    return {
        "likes": int(row[0] or 0),
        "comments": int(row[1] or 0),
        "follows": int(row[2] or 0),
        "unfollows": int(row[3] or 0),
    }


def remaining_allowance(usage, args):
    return {
        "likes": max(0, args.max_likes_daily - usage["likes"]),
        "comments": max(0, args.max_comments_daily - usage["comments"]),
        "follows": max(0, args.max_follows_daily - usage["follows"]),
    }


def remaining_unfollows(usage, args):
    return max(0, args.max_unfollows_daily - usage["unfollows"])


def tasks_without_allowance(usage, args, tasks):
    """Return the selected tasks whose daily allowance is already used up."""
    blocked = []
    allowance = remaining_allowance(usage, args)

    if TASK_HASHTAGS in tasks and min(allowance.values()) <= 0:
        blocked.append(TASK_HASHTAGS)
    if (
        TASK_COMMENTS in tasks
        and args.like_comments_accounts > 0
        and allowance["likes"] <= 0
    ):
        blocked.append(TASK_COMMENTS)
    if (
        TASK_UNFOLLOW in tasks
        and args.unfollow_after_days > 0
        and remaining_unfollows(usage, args) <= 0
    ):
        blocked.append(TASK_UNFOLLOW)

    return blocked


def print_summary(hashtags, comments, replies, args):
    tasks = getattr(args, "tasks", set(ALL_TASKS))
    print("Tasks for this run:")
    for task in ALL_TASKS:
        marker = "[x]" if task in tasks else "[ ]"
        print("  {} {} - {}".format(marker, task, TASK_DESCRIPTIONS[task]))
    print()
    if TASK_HASHTAGS in tasks:
        print("Hashtags ({}):".format(len(hashtags)))
        print("  " + " ".join("#{}".format(tag) for tag in hashtags))
        print()
    print(
        "Comments: {} available, cycled through without repeating until "
        "all are used.".format(len(comments))
    )
    print(
        "Replies: {} available, used when replying to comments.".format(
            len(replies)
        )
    )
    print()
    print(
        "Posts per run: up to {} ({} per hashtag).".format(
            args.amount * len(hashtags), args.amount
        )
    )
    if args.candidates_per_hashtag > args.amount:
        print(
            "Candidates: up to {} posts inspected per hashtag until {} "
            "usable post(s) are handled.".format(
                args.candidates_per_hashtag, args.amount
            )
        )
    print(
        "Action rates: follow {}% of posts, comment on {}% of posts.".format(
            clamp_percentage(args.follow_percentage),
            clamp_percentage(args.comment_percentage),
        )
    )
    if args.like_comments_accounts > 0:
        print(
            "Comment engagement: likes up to {} comment(s) per post on {} "
            "post(s) of {} followed account(s); replies to about {}% of "
            "liked comments.".format(
                args.like_comments_per_post,
                args.like_comments_posts,
                args.like_comments_accounts,
                clamp_percentage(args.reply_percentage),
            )
        )
    else:
        print("Comment engagement: disabled.")
    if args.story_accounts > 0:
        print(
            "Stories: watches up to {} followed account(s) per run.".format(
                args.story_accounts
            )
        )
    else:
        print("Stories: disabled.")
    if args.max_follow_difference > 0:
        print(
            "Follow filter: only follows accounts whose follower and "
            "following counts differ by at most {} (likes and comments are "
            "never limited by it).".format(args.max_follow_difference)
        )
    else:
        print("Follow filter: disabled (follows are not ratio-checked).")
    if args.unfollow_after_days:
        print(
            "Unfollow check: accounts that have not followed back within "
            "{} day(s) are unfollowed and never followed again.".format(
                args.unfollow_after_days
            )
        )
    else:
        print("Unfollow check: disabled.")
    print(
        "Safety caps: likes {}/hour, {}/day | comments {}/hour, {}/day | "
        "follows {}/hour, {}/day | unfollows {}/hour, {}/day".format(
            args.max_likes_hourly,
            args.max_likes_daily,
            args.max_comments_hourly,
            args.max_comments_daily,
            args.max_follows_hourly,
            args.max_follows_daily,
            args.max_unfollows_hourly,
            args.max_unfollows_daily,
        )
    )
    print(
        "Pauses: {} hashtags per group, then {}-{} minute break; "
        "run limit {} minutes.".format(
            args.chunk_size,
            args.chunk_pause_min,
            args.chunk_pause_max,
            args.max_run_minutes,
        )
    )
    print(
        "Cooldown between runs: {} hour(s).".format(args.min_hours_between_runs)
    )
    if args.max_post_age_days:
        print(
            "Activity check: only posts published in the last {} days are "
            "eligible.".format(args.max_post_age_days)
        )
    else:
        print("Activity check: disabled (old posts may be used).")


def print_usage_report(username, usage, args, when="before this run"):
    print()
    print("Today's usage for '{}' {}:".format(username, when))
    print(
        "  likes    {}/{}   ({} left)".format(
            usage["likes"],
            args.max_likes_daily,
            max(0, args.max_likes_daily - usage["likes"]),
        )
    )
    print(
        "  comments {}/{}   ({} left)".format(
            usage["comments"],
            args.max_comments_daily,
            max(0, args.max_comments_daily - usage["comments"]),
        )
    )
    print(
        "  follows  {}/{}   ({} left)".format(
            usage["follows"],
            args.max_follows_daily,
            max(0, args.max_follows_daily - usage["follows"]),
        )
    )
    print(
        "  unfollows {}/{}   ({} left)".format(
            usage["unfollows"],
            args.max_unfollows_daily,
            max(0, args.max_unfollows_daily - usage["unfollows"]),
        )
    )


def build_quota(session, args):
    """Let InstaPy enforce the same caps against its persistent database."""
    session.set_quota_supervisor(
        enabled=True,
        sleepyhead=False,
        stochastic_flow=False,
        notify_me=False,
        peak_likes_hourly=args.max_likes_hourly,
        peak_likes_daily=args.max_likes_daily,
        peak_comments_hourly=args.max_comments_hourly,
        peak_comments_daily=args.max_comments_daily,
        peak_follows_hourly=args.max_follows_hourly,
        peak_follows_daily=args.max_follows_daily,
        peak_unfollows_hourly=args.max_unfollows_hourly,
        peak_unfollows_daily=args.max_unfollows_daily,
    )


def validate_args(args):
    if args.amount < 1:
        sys.exit("--amount must be at least 1.")
    if args.amount > 10:
        sys.exit("For safety, --amount cannot be higher than 10.")
    if args.candidates_per_hashtag < 1:
        sys.exit("--candidates-per-hashtag must be at least 1.")
    if args.candidates_per_hashtag > 50:
        sys.exit("For safety, --candidates-per-hashtag cannot be higher than 50.")
    if args.chunk_size < 1:
        sys.exit("--chunk-size must be at least 1.")
    if args.max_run_minutes < 1:
        sys.exit("--max-run-minutes must be at least 1.")
    if args.max_post_age_days < 0:
        sys.exit("--max-post-age-days cannot be negative (use 0 to disable).")
    if args.max_follow_difference < 0:
        sys.exit("--max-follow-difference cannot be negative (use 0 to disable).")
    if args.unfollow_after_days < 0:
        sys.exit("--unfollow-after-days cannot be negative (use 0 to disable).")
    if args.min_hours_between_runs < 0:
        sys.exit("--min-hours-between-runs cannot be negative.")
    if args.chunk_pause_min < 0 or args.chunk_pause_max < args.chunk_pause_min:
        sys.exit(
            "Use a valid pause range, e.g. --chunk-pause-min 2 "
            "--chunk-pause-max 4."
        )
    if not 0 <= args.reply_percentage <= 100:
        sys.exit("--reply-percentage must be between 0 and 100.")
    if args.like_comments_accounts < 0:
        sys.exit("--like-comments-accounts cannot be negative.")
    if args.like_comments_posts < 0:
        sys.exit("--like-comments-posts cannot be negative.")
    if args.like_comments_per_post < 0:
        sys.exit("--like-comments-per-post cannot be negative.")
    if args.like_comments_accounts > 0:
        if args.like_comments_posts < 1:
            sys.exit("--like-comments-posts must be at least 1.")
        if args.like_comments_per_post < 1:
            sys.exit("--like-comments-per-post must be at least 1.")
    if args.story_accounts < 0:
        sys.exit("--story-accounts cannot be negative.")
    for name in (
        "max_likes_hourly",
        "max_likes_daily",
        "max_comments_hourly",
        "max_comments_daily",
        "max_follows_hourly",
        "max_follows_daily",
        "max_unfollows_hourly",
        "max_unfollows_daily",
    ):
        if getattr(args, name) < 1:
            sys.exit("--{} must be at least 1.".format(name.replace("_", "-")))

    # Hard ceilings: even an explicit override cannot turn this into a
    # high-volume bot. The defaults are much lower than these values.
    ceilings = {
        "max_likes_hourly": 50,
        "max_likes_daily": 200,
        "max_comments_hourly": 12,
        "max_comments_daily": 40,
        "max_follows_hourly": 20,
        "max_follows_daily": 80,
        "max_unfollows_hourly": 20,
        "max_unfollows_daily": 80,
    }
    for name, ceiling in ceilings.items():
        if getattr(args, name) > ceiling:
            sys.exit(
                "For safety, --{} cannot be higher than {}.".format(
                    name.replace("_", "-"), ceiling
                )
            )

    # Comment engagement is not tracked by InstaPy's quota supervisor as a
    # separate action, so keep it small with hard ceilings as well.
    engagement_ceilings = {
        "like_comments_accounts": 10,
        "like_comments_posts": 3,
        "like_comments_per_post": 5,
        "story_accounts": 20,
    }
    for name, ceiling in engagement_ceilings.items():
        if getattr(args, name) > ceiling:
            sys.exit(
                "For safety, --{} cannot be higher than {}.".format(
                    name.replace("_", "-"), ceiling
                )
            )


def unfollow_nonfollowers(session, args, username):
    """Unfollow users who have not followed back in time.

    The usernames that leave InstaPy's followed pool are written to the
    follow-restriction table, so the follow code will not follow them again.
    """
    if args.unfollow_after_days <= 0:
        return set()

    usage = today_usage(username)
    allowed_unfollows = remaining_unfollows(usage, args)

    if allowed_unfollows <= 0:
        print("Daily unfollow cap reached; skipping unfollows.")
        return set()

    before_pool = followed_pool_usernames(session.logfolder, username)
    session.unfollow_users(
        amount=allowed_unfollows,
        nonFollowers=True,
        style="FIFO",
        unfollow_after=args.unfollow_after_days * 24 * 60 * 60,
        sleep_delay=600,
    )
    after_pool = followed_pool_usernames(session.logfolder, username)
    unfollowed = before_pool - after_pool

    for person in sorted(unfollowed):
        follow_restriction("write", person, None, session.logger)

    if unfollowed:
        print(
            "Unfollowed {} account(s) that did not follow back within {} "
            "day(s); they will not be followed again.".format(
                len(unfollowed), args.unfollow_after_days
            )
        )

    return unfollowed


def _engagement_candidates(session, args, username, started_at, purpose):
    """Return a shuffled list of followed accounts, or ``None`` to skip."""
    pool = followed_pool_usernames(session.logfolder, username)
    pool.discard(username)
    if not pool:
        print("No followed accounts yet; skipping {}.".format(purpose))
        return None

    elapsed_minutes = (time.monotonic() - started_at) / 60
    if elapsed_minutes >= args.max_run_minutes:
        print("Run time limit reached; skipping {}.".format(purpose))
        return None

    candidates = sorted(pool)
    random.shuffle(candidates)
    return candidates


def run_story_engagement(session, args, username, started_at):
    """Watch stories of followed accounts."""
    if args.story_accounts <= 0:
        return

    candidates = _engagement_candidates(
        session, args, username, started_at, "story watching"
    )
    if candidates is None:
        return

    story_targets = candidates[: args.story_accounts]
    print(
        "Watching stories of up to {} followed account(s)...".format(
            len(story_targets)
        )
    )
    try:
        session.story_by_users(story_targets)
    except Exception as error:  # one bad story must not stop the run
        print("Story watching skipped: {}".format(error))


def run_comment_engagement(session, args, username, started_at):
    """Like comments on followed accounts' recent posts and reply to some."""
    if args.like_comments_accounts <= 0:
        return

    candidates = _engagement_candidates(
        session, args, username, started_at, "comment engagement"
    )
    if candidates is None:
        return

    usage = today_usage(username)
    remaining = remaining_allowance(usage, args)
    if remaining["likes"] <= 0:
        print("Daily like cap reached; skipping comment engagement.")
        return

    sample = candidates[: args.like_comments_accounts]
    print(
        "Comment engagement: liking up to {} comment(s) per post on {} "
        "recent post(s) of {} followed account(s)...".format(
            args.like_comments_per_post,
            args.like_comments_posts,
            len(sample),
        )
    )
    try:
        session.interact_by_comments(
            usernames=sample,
            posts_amount=args.like_comments_posts,
            comments_per_post=args.like_comments_per_post,
            reply=args.reply_percentage > 0,
            interact=False,
            randomize=True,
        )
    except Exception as error:  # extra engagement must never break a run
        print("Comment engagement skipped: {}".format(error))


def run_growth_engagement(session, args, username, started_at):
    """Run both extra engagement tasks (stories, then comment likes).

    Kept as a convenience wrapper; ``run_session`` calls the two tasks
    separately so either one can be selected on its own.
    """
    run_story_engagement(session, args, username, started_at)
    run_comment_engagement(session, args, username, started_at)


def run_session(
    args,
    hashtags,
    comments,
    replies,
    username,
    password,
    state_path=None,
    state=None,
):
    """Create the InstaPy session and process hashtags one at a time."""
    session = InstaPy(
        username=username,
        password=password,
        headless_browser=args.headless,
    )

    run_tags = list(hashtags)
    started_at = time.monotonic()
    tasks = getattr(args, "tasks", set(ALL_TASKS))

    with smart_run(session):
        # InstaPy opens Firefox at 414x896 (a phone-sized viewport). At that
        # width Instagram serves a reduced layout: the comment box is missing
        # and the follow button uses hidden icon text. A desktop viewport makes
        # the normal comment form and profile buttons available.
        try:
            session.browser.set_window_size(1280, 900)
        except Exception:
            pass

        # Posts found through hashtags are public, so the private-account
        # check is unnecessary. Disabling it avoids an extra profile visit
        # (and its slow data lookup) for every single post.
        session.set_skip_users(skip_private=False)

        # Only follow accounts whose follower and following counts are close
        # enough that a follow-back is plausible. This is a follow-only filter:
        # posts from other accounts are still liked and commented on.
        if args.max_follow_difference > 0:
            session.set_follow_difference_limit(
                max_difference=args.max_follow_difference
            )
        else:
            session.set_follow_difference_limit(enabled=False)

        session.set_do_follow(
            enabled=True,
            percentage=clamp_percentage(args.follow_percentage),
            times=1,
        )
        session.set_do_comment(
            enabled=True,
            percentage=clamp_percentage(args.comment_percentage),
        )
        session.set_comments(comments)
        session.set_do_like(enabled=True, percentage=100)

        # Replying to comments and watching stories are extra ways to keep
        # the account visible. Replies are posted through comment_image, so
        # they count toward the normal comment caps.
        session.set_do_reply_to_comments(
            enabled=args.reply_percentage > 0,
            percentage=clamp_percentage(args.reply_percentage),
        )
        session.set_comment_replies(replies)
        session.set_do_story(
            enabled=args.story_accounts > 0,
            percentage=100,
            simulate=True,
        )

        # Only act on accounts that are currently active: a post older than
        # this limit is skipped before liking, commenting or following.
        session.set_max_post_age_days(args.max_post_age_days)

        # Long, randomized pauses after every action.
        session.set_action_delays(
            enabled=True,
            like=8,
            comment=30,
            follow=45,
            randomize=True,
            random_range_from=70,
            random_range_to=150,
        )

        build_quota(session, args)

        # Unfollow accounts that have had enough time to follow back. Users
        # removed from the followed pool are recorded in InstaPy's follow
        # restriction table so they are never followed again.
        if TASK_UNFOLLOW in tasks:
            unfollow_nonfollowers(session, args, username)

        if TASK_HASHTAGS in tasks:
            for index, tag in enumerate(run_tags, 1):
                usage = today_usage(username)
                remaining = remaining_allowance(usage, args)

                if min(remaining.values()) <= 0:
                    print(
                        "Daily safety cap reached (likes {}, comments {}, "
                        "follows {}). Stopping.".format(
                            usage["likes"], usage["comments"], usage["follows"]
                        )
                    )
                    break

                elapsed_minutes = (time.monotonic() - started_at) / 60
                if elapsed_minutes >= args.max_run_minutes:
                    print(
                        "Run time limit of {} minutes reached. Stopping.".format(
                            args.max_run_minutes
                        )
                    )
                    break

                print(
                    "Hashtag [{}/{}]: #{}".format(index, len(run_tags), tag)
                )
                session.like_by_tags(
                    [quote(tag, safe="")],
                    amount=max(args.amount, args.candidates_per_hashtag),
                    max_posts_per_tag=args.amount,
                    skip_top_posts=not args.include_top_posts,
                    randomize=True,
                )

                # Remember where the next run should continue.
                if state is not None and state_path:
                    order = state.get("hashtag_order") or run_tags
                    state["hashtag_position"] = (
                        state.get("hashtag_position", 0) + 1
                    ) % len(order)
                    save_state(state_path, state)

                is_last_tag = index == len(run_tags)
                group_finished = index % args.chunk_size == 0
                if not is_last_tag and group_finished:
                    pause_seconds = random.uniform(
                        args.chunk_pause_min * 60, args.chunk_pause_max * 60
                    )
                    print(
                        "Pausing {:.0f} seconds before the next group...".format(
                            pause_seconds
                        )
                    )
                    time.sleep(pause_seconds)

        # Extra engagement uses only accounts the bot already follows. Each
        # task is independent, so either one can be selected on its own.
        if TASK_STORIES in tasks:
            run_story_engagement(session, args, username, started_at)

        if TASK_COMMENTS in tasks:
            run_comment_engagement(session, args, username, started_at)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    args = parse_args()
    if should_prompt(args):
        run_interactive(args)
    validate_args(args)

    tasks = getattr(args, "tasks", selected_tasks(args))

    username = args.username or os.environ.get("INSTA_USER")
    password = args.password or os.environ.get("INSTA_PW")

    if args.tags_file:
        if not os.path.isfile(args.tags_file):
            sys.exit("Tags file not found: {}".format(args.tags_file))
        hashtags = collect_hashtags(read_lines(args.tags_file))
    else:
        hashtags = collect_hashtags(DEFAULT_HASHTAGS)

    if args.comments_file:
        if not os.path.isfile(args.comments_file):
            sys.exit("Comments file not found: {}".format(args.comments_file))
        comments = collect_comments(read_lines(args.comments_file))
    else:
        comments = collect_comments(DEFAULT_COMMENTS)

    if args.replies_file:
        if not os.path.isfile(args.replies_file):
            sys.exit("Replies file not found: {}".format(args.replies_file))
        replies = collect_comments(read_lines(args.replies_file))
    else:
        replies = collect_comments(DEFAULT_REPLIES)

    if TASK_HASHTAGS in tasks:
        if not hashtags:
            sys.exit("No hashtags to work with.")
        if not comments:
            sys.exit("No comments to post.")

    print_summary(hashtags, comments, replies, args)

    if args.dry_run:
        print("\nDry run only. No browser was opened.")
        return 0

    if not username:
        sys.exit("Set INSTA_USER or pass --username.")

    workspace = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workspace")
    set_workspace(path=workspace)
    workspace_path = get_workspace()["path"]

    session_file = saved_session_path(username, workspace_path)
    has_session = os.path.isfile(session_file)

    if not password and not has_session:
        sys.exit(
            "No saved session found. Run once with INSTA_PW / --password so "
            "InstaPy can save a session, then later runs can reuse it."
        )

    if has_session:
        print("\nSaved session found: {}".format(session_file))
        print("Logging in with the saved session (no password needed).")
    else:
        print("\nNo saved session yet; logging in with username and password.")

    usage = today_usage(username)
    print_usage_report(username, usage, args)
    blocked = tasks_without_allowance(usage, args, tasks)
    if blocked:
        print(
            "Daily safety cap already reached for: {}. "
            "Those tasks will be skipped.".format(", ".join(blocked))
        )
    if set(blocked) >= set(tasks):
        sys.exit("Every selected task has reached its daily cap. Try again tomorrow.")

    state_path = os.path.join(workspace_path, STATE_FILENAME)
    state = load_state(state_path)
    if not check_run_gap(state, args.min_hours_between_runs, tasks):
        return 1

    lock_path = os.path.join(workspace_path, LOCK_FILENAME)
    if not acquire_lock(lock_path, args.max_run_minutes + 15):
        sys.exit("Another run appears to be active. Wait for it to finish.")

    try:
        now_iso = datetime.now().isoformat(timespec="seconds")
        state["last_run"] = now_iso
        last_runs = state.get("last_run_by_task")
        if not isinstance(last_runs, dict):
            last_runs = {}
        for task in tasks:
            last_runs[task] = now_iso
        state["last_run_by_task"] = last_runs

        # Only touch the hashtag rotation when the hashtag task is selected.
        run_tags = []
        if TASK_HASHTAGS in tasks:
            order, position = build_run_order(hashtags, state)
            run_tags = order[position:] + order[:position]
            print(
                "Hashtag cycle position: {}/{}".format(position, len(order))
            )
        save_state(state_path, state)
        run_session(
            args,
            run_tags,
            comments,
            replies,
            username,
            password,
            state_path,
            state,
        )
    finally:
        release_lock(lock_path)

    print("\nRun finished. Today's final usage:")
    print_usage_report(username, today_usage(username), args, "after this run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
