# -*- coding: utf-8 -*-
""" Module which handles the commenting features """
# import built-in & third-party modules
import os
import random

import emoji

# import exceptions
from selenium.common.exceptions import (
    InvalidElementStateException,
    NoSuchElementException,
    WebDriverException,
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from .event import Event
from .quota_supervisor import quota_supervisor

# import InstaPy modules
from .time_util import sleep
from .util import (
    add_user_to_blacklist,
    click_element,
    evaluate_mandatory_words,
    explicit_wait,
    get_action_delay,
    getMediaData,
    update_activity,
    web_address_navigator,
)
from .xpath import read_xpath

# Shuffled decks of comments, keyed by the comment list they belong to. Each
# deck is consumed one comment at a time and refilled only after every comment
# was posted once, so the same text is not posted repeatedly.
_comment_decks = {}
_last_comments = {}


def choose_comment(comments):
    """Return the next comment without repeating recent ones.

    All comments are used once (in random order) before any comment can be
    chosen again. This prevents the bot from posting the same comment on many
    posts in a row, which looks spammy and can hurt the account.
    """
    if not comments:
        return ""

    if len(comments) == 1:
        return comments[0]

    key = tuple(comments)
    deck = _comment_decks.get(key)

    if not deck:
        deck = list(comments)
        random.shuffle(deck)
        # Do not start a new cycle with the comment that ended the previous
        # cycle; the deck is consumed from the end.
        last = _last_comments.get(key)
        if len(deck) > 1 and deck[-1] == last:
            deck[-1], deck[0] = deck[0], deck[-1]

    comment = deck.pop()
    _comment_decks[key] = deck
    _last_comments[key] = comment
    return comment


def _find_elements_fast(browser, by, value):
    """Find elements without waiting for the full implicit timeout.

    InstaPy sets a long implicit wait (usually 25s). Optional selectors such as
    the comment box do not exist in every layout, and asking for them with that
    wait made the bot stall for minutes. Use a zero wait and restore the
    previous setting afterwards.
    """
    try:
        original_timeout = browser.timeouts.implicit_wait
    except Exception:
        original_timeout = None

    # If the driver cannot report its timeout, do not risk changing it.
    if original_timeout is None:
        try:
            return browser.find_elements(by, value)
        except Exception:
            return []

    try:
        browser.implicitly_wait(0)
        return browser.find_elements(by, value)
    except Exception:
        return []
    finally:
        try:
            browser.implicitly_wait(original_timeout)
        except Exception:
            pass


def get_comment_input(browser):
    """Return the visible comment input, trying the known IG layouts."""
    for xpath_name in ("comment_input", "placeholder", "contenteditable"):
        candidates = _find_elements_fast(
            browser, By.XPATH, read_xpath(get_comment_input.__name__, xpath_name)
        )

        # Typing makes React re-render the composer, so some of the elements
        # found above can go stale before `is_displayed()` is called.
        visible = []
        for element in candidates:
            try:
                if element.is_displayed():
                    visible.append(element)
            except WebDriverException:
                continue
        if visible:
            return visible

    return []


def open_comment_section(browser, logger):
    missing_comment_elem_warning = (
        "--> Comment Button Not Found!"
        "\t~may cause issues with browser windows of smaller widths"
    )

    # The input can already be visible (wide layout); do not click anything in
    # that case, as the comment icon toggles the panel and could close it.
    if get_comment_input(browser):
        return

    comment_elems = _find_elements_fast(
        browser, By.XPATH, read_xpath(open_comment_section.__name__, "comment_elem")
    )

    comment_elem = None
    for element in comment_elems:
        try:
            if element.is_displayed():
                comment_elem = element
                break
        except WebDriverException:
            continue

    if comment_elem is not None:
        try:
            click_element(browser, comment_elem)
            # Give the comments panel time to slide in.
            sleep(2)
        except WebDriverException:
            logger.warning(missing_comment_elem_warning)
    else:
        logger.warning(missing_comment_elem_warning)


def comment_image(browser, username, comments, blacklist, logger, logfolder):
    """Checks if it should comment on the image"""
    # check action availability
    if quota_supervisor("comments") == "jump":
        return False, "jumped"

    rand_comment = choose_comment(comments).format(username)
    rand_comment = emoji.demojize(rand_comment)
    try:
        rand_comment = emoji.emojize(rand_comment, use_aliases=True)
    except TypeError:
        # emoji>=2.0 removed the `use_aliases` argument
        rand_comment = emoji.emojize(rand_comment)

    open_comment_section(browser, logger)
    # wait, to avoid crash
    sleep(3)
    comment_input = get_comment_input(browser)

    comment_to_be_sent = rand_comment

    # On slower connections / narrow layouts the input can take a few more
    # seconds to appear after the comments panel opens.
    if not comment_input:
        for _ in range(5):
            sleep(2)
            comment_input = get_comment_input(browser)
            if comment_input:
                break

    if not comment_input:
        logger.warning(
            "--> Comment Action Likely Failed!\t~comment Element was not found"
        )
        return False, "commenting disabled"

    def remaining_comment_text():
        inputs = get_comment_input(browser)
        if not inputs:
            return ""
        try:
            return (
                inputs[0].get_attribute("value") or inputs[0].text or ""
            ).strip()
        except WebDriverException:
            return ""

    def post_button():
        for element in _find_elements_fast(
            browser, By.XPATH, "//button[normalize-space(.)='Post']"
        ):
            try:
                if element.is_displayed() and element.is_enabled():
                    return element
            except WebDriverException:
                continue
        return None

    submitted = False
    try:
        # click on textarea/comment box and enter comment
        (
            ActionChains(browser)
            .move_to_element(comment_input[0])
            .click()
            .send_keys(comment_to_be_sent)
            .perform()
        )
        # wait, to avoid crash
        sleep(2)

        # Submit with the "Post" button when available (desktop layout);
        # otherwise fall back to Enter. The composer is re-rendered after
        # typing, so always look the element up again before pressing it.
        for attempt in range(3):
            if attempt == 0 or remaining_comment_text():
                button = post_button()
                if button is not None:
                    click_element(browser, button)
                else:
                    fresh_input = get_comment_input(browser)
                    if fresh_input:
                        (
                            ActionChains(browser)
                            .move_to_element(fresh_input[0])
                            .send_keys(Keys.ENTER)
                            .perform()
                        )

            for _ in range(5):
                sleep(1)
                if not remaining_comment_text():
                    submitted = True
                    break
            if submitted:
                break

    except InvalidElementStateException:
        logger.warning(
            "--> Comment Action Likely Failed!"
            "\t~encountered `InvalidElementStateException` :/"
        )
        return False, "invalid element state"
    except WebDriverException as ex:
        logger.warning(
            "--> Comment Action Likely Failed!\t~{}".format(ex)
        )
        return False, "webdriver error"

    if not submitted:
        logger.warning("--> Comment was typed but Instagram did not submit it")
        return False, "comment not submitted"

    update_activity(
        browser,
        action="comments",
        state=None,
        logfolder=logfolder,
        logger=logger,
    )

    if blacklist["enabled"] is True:
        action = "commented"
        add_user_to_blacklist(
            username, blacklist["campaign"], action, logger, logfolder
        )

    logger.info("--> Commented: {}".format(rand_comment))
    Event().commented(username)

    # get the post-comment delay time to sleep
    naply = get_action_delay("comment")
    sleep(naply)

    return True, "success"


def verify_commenting(browser, maximum, minimum, logger):
    """
     Get the amount of existing existing comments and
    compare it against maximum & minimum values defined by user
    """

    commenting_state, msg = is_commenting_enabled(browser, logger)
    if commenting_state is not True:
        disapproval_reason = "--> Not commenting! {}".format(msg)
        return False, disapproval_reason

    comments_count, msg = get_comments_count(browser, logger)
    if comments_count is None:
        disapproval_reason = "--> Not commenting! {}".format(msg)
        return False, disapproval_reason

    if maximum is not None and comments_count > maximum:
        disapproval_reason = "Not commented on this post! ~more comments exist off maximum limit at {}".format(
            comments_count
        )
        return False, disapproval_reason

    elif minimum is not None and comments_count < minimum:
        disapproval_reason = "Not commented on this post! ~less comments exist off minimum limit at {}".format(
            comments_count
        )
        return False, disapproval_reason

    return True, "Approval"


def verify_mandatory_words(
    mand_words,
    comments,
    browser,
    logger,
):
    if len(mand_words) > 0 or isinstance(comments[0], dict):
        try:
            post_desc = getMediaData(
                "edge_media_to_caption.edges.0.node.text", browser
            ).lower()

        except Exception:
            post_desc = None

        try:
            first_comment = getMediaData(
                "edge_media_to_parent_comment.edges.0.node.text", browser
            ).lower()

        except Exception:
            first_comment = None

        if post_desc is None and first_comment is None:
            return False, [], "couldn't get post description and comments"

        text = (
            post_desc
            if post_desc is not None
            else "" + " " + first_comment
            if first_comment is not None
            else ""
        )

        if len(mand_words) > 0:
            if not evaluate_mandatory_words(text, mand_words):
                return False, [], "mandatory words not in post desc"

        if isinstance(comments[0], dict):
            # The comments definition is a compound definition of conditions and comments
            for compund_comment in comments:
                if (
                    "mandatory_words" not in compund_comment
                    or evaluate_mandatory_words(
                        text, compund_comment["mandatory_words"]
                    )
                ):
                    return True, compund_comment["comments"], "Approval"
            return (
                False,
                [],
                "Coulnd't match the mandatory words in any comment definition",
            )

    return True, comments, "Approval"


def get_comments_on_post(
    browser, owner, poster, amount, post_link, ignore_users, randomize, logger
):
    """Fetch comments data on posts"""
    web_address_navigator(browser, post_link)

    comments = []
    commenters = []

    if randomize is True:
        amount = amount * 3

    # check if commenting on the post is enabled
    (commenting_approved, disapproval_reason,) = verify_commenting(
        browser,
        None,
        None,
        logger,
    )
    if not commenting_approved:
        logger.info(disapproval_reason)
        return None

    # get comments & commenters information path
    like_button_full_XPath = read_xpath(
        get_comments_on_post.__name__, "like_button_full_XPath"
    )
    unlike_button_full_XPath = read_xpath(
        get_comments_on_post.__name__, "unlike_button_full_XPath"
    )

    # wait for page fully load [IMPORTANT!]
    explicit_wait(browser, "PFL", [], logger, 10)

    try:
        all_comment_like_buttons = browser.find_elements(
            By.XPATH, like_button_full_XPath
        )

        if all_comment_like_buttons:
            commenter = None
            comment = None

            data = getMediaData("edge_media_to_parent_comment", browser)
            if not data:
                logger.info("Could not grab comments from this post.")
                return None

            for value in data["edges"]:
                commenter = value["node"]["owner"]["username"]
                comment = value["node"]["text"]

                if (
                    commenter
                    and commenter not in commenters
                    and commenter not in [owner, poster, ignore_users]
                    and comment
                ):
                    commenters.append(commenter)
                    comments.append(comment)
                else:
                    logger.info("Could not grab any commenter from this post")

        else:
            comment_unlike_buttons = browser.find_elements(
                By.XPATH, unlike_button_full_XPath
            )

            if comment_unlike_buttons:
                logger.info(
                    "Grabbed {} comment(s) on this post and already liked.".format(
                        len(comment_unlike_buttons)
                    )
                )
            else:
                logger.info("There are no any comments available on this post.")
            return None

    except NoSuchElementException:
        logger.info("Failed to grab comments on this post.")
        return None

    if not comments:
        logger.info("Could not grab any usable comments from this post...")
        return None

    else:
        comment_data = list(zip(commenters, comments))
        if randomize is True:
            random.shuffle(comment_data)

        logger.info(
            "Grabbed only {} usable comment(s) from this post...".format(
                len(comment_data)
            )
        )

        return comment_data


def is_commenting_enabled(browser, logger):
    """Find out if commenting on the post is enabled"""

    comments_disabled = getMediaData("comments_disabled", browser)

    if comments_disabled is None:
        return True, "Could not determine whether comments are enabled"

    if comments_disabled is True:
        msg = "Comments are disabled for this post."
        return False, msg

    return True, "Success"


def get_comments_count(browser, logger):
    """Get the number of total comments in the post"""

    comments_count = getMediaData("edge_media_preview_comment.count", browser)
    return (comments_count if comments_count is not None else 0), "Success"


def _commented_posts_path(logfolder):
    if not logfolder:
        return None
    return os.path.join(logfolder, "commented_posts.txt")


def _post_key(link):
    """Reduce a post URL to its shortcode / unique path."""
    return (link or "").rstrip("/").split("/")[-1]


def already_commented_locally(link, logfolder):
    path = _commented_posts_path(logfolder)
    if not path or not os.path.isfile(path):
        return False

    key = _post_key(link)
    try:
        with open(path, "r", encoding="utf-8") as file_handle:
            return any(line.strip() == key for line in file_handle)
    except OSError:
        return False


def record_commented_post(link, logfolder):
    path = _commented_posts_path(logfolder)
    if not path:
        return

    key = _post_key(link)
    if not key or already_commented_locally(link, logfolder):
        return

    try:
        os.makedirs(logfolder, exist_ok=True)
        with open(path, "a", encoding="utf-8") as file_handle:
            file_handle.write(key + "\n")
    except OSError:
        pass


def verify_commented_image(browser, link, owner, logger, logfolder=None):
    """Determine if this account has already commented on the post.

    Instagram no longer exposes the old ``_sharedData`` / ``__additionalData``
    JSON, so the previous check returned "already commented" for every post and
    blocked all comments. Use the local record first and only treat a positive
    remote answer as conclusive.
    """

    if already_commented_locally(link, logfolder):
        return (
            True,
            "--> The post was already commented on by this bot, skipping...",
        )

    web_address_navigator(browser, link)

    # wait for page fully load [IMPORTANT!]
    explicit_wait(browser, "PFL", [], logger, 10)

    try:
        data = getMediaData("edge_media_to_parent_comment", browser)
        if not data or not data.get("edges"):
            # The data endpoint is gone. Do not skip the post: the local
            # record above already prevents duplicate comments by this bot.
            return (
                None,
                "--> Comment history unavailable, proceeding to comment...",
            )

        for value in data["edges"]:
            commenter = value["node"]["owner"]["username"]

            if commenter and commenter == owner:
                message = (
                    "--> The post has already been commented on before: "
                    "'{}'".format(value["node"]["text"])
                )
                return True, message

    except (NoSuchElementException, KeyError, IndexError, TypeError):
        # Cannot be determined remotely; fall through to commenting.
        return (
            None,
            "--> Could not read existing comments, proceeding to comment...",
        )

    message = "--> No comment from this account found, trying to comment..."
    return None, message


def process_comments(
    comments,
    clarifai_comments,
    delimit_commenting,
    max_comments,
    min_comments,
    comments_mandatory_words,
    owner,
    user_name,
    blacklist,
    browser,
    link,
    logger,
    logfolder,
    publish=True,
):

    # comments
    if delimit_commenting:
        (commenting_approved, disapproval_reason,) = verify_commenting(
            browser,
            max_comments,
            min_comments,
            logger,
        )
        if not commenting_approved:
            logger.info(disapproval_reason)
            return False

    (
        commenting_approved,
        selected_comments,
        disapproval_reason,
    ) = verify_mandatory_words(
        comments_mandatory_words,
        comments,
        browser,
        logger,
    )

    if not commenting_approved:
        logger.info(disapproval_reason)
        return False

    if len(clarifai_comments) > 0:
        selected_comments = clarifai_comments

    # smart commenting
    if comments and publish:
        # Check if InstaPy already commented on this post, it could be the
        # case that the image has been liked (manually) but not commented, so
        # we want to comment the post like usually we do.
        commented_image, message = verify_commented_image(
            browser, link, owner, logger, logfolder
        )

        if commented_image:
            # The post has already been commented, either manually or InstaPy
            # Commenting twice by InstaPy user is not allowed by now or could
            # not get comments on this post to check if InstaPy user commented
            # before, so will not comment until next check
            logger.info(message)
            return False
        else:
            logger.info(message)

        comment_state, _ = comment_image(
            browser,
            user_name,
            selected_comments,
            blacklist,
            logger,
            logfolder,
        )

        if comment_state:
            record_commented_post(link, logfolder)

        # Return to the target uset page
        user_link = "https://www.instagram.com/{}/".format(user_name)
        web_address_navigator(browser, user_link)

        return comment_state
