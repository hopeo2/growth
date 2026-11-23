""" Module that handles the like features """
# import built-in & third-party modules
import random
import re
from datetime import datetime, timedelta, timezone
from re import findall

# import exceptions
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.common.by import By

# import InstaPy modules
from .comment_util import open_comment_section
from .constants import (
    MEDIA_ALL_TYPES,
    MEDIA_CAROUSEL,
    MEDIA_CLIP,
    MEDIA_IGTV,
    MEDIA_PHOTO,
    MEDIA_VIDEO,
)
from .event import Event
from .follow_util import get_following_status
from .quota_supervisor import quota_supervisor
from .time_util import sleep
from .util import (
    add_user_to_blacklist,
    click_element,
    evaluate_mandatory_words,
    explicit_wait,
    extract_text_from_element,
    format_number,
    get_action_delay,
    get_additional_data,
    get_number_of_posts,
    is_page_available,
    is_private_profile,
    update_activity,
    web_address_navigator,
)
from .xpath import read_xpath


def _find_elements_fast(browser, by, value):
    """Like ``find_elements`` but without the long implicit wait.

    InstaPy sets a 25 second implicit wait. Optional selectors (the video
    play button, per-comment like icons, ...) are absent on many posts, and
    each miss used to stall the bot for 25 seconds. Restore the original
    timeout afterwards.
    """
    try:
        original_timeout = browser.timeouts.implicit_wait
    except Exception:
        original_timeout = None

    if original_timeout is None:
        try:
            return browser.find_elements(by, value)
        except WebDriverException:
            return []

    try:
        browser.implicitly_wait(0)
        return browser.find_elements(by, value)
    except WebDriverException:
        return []
    finally:
        try:
            browser.implicitly_wait(original_timeout)
        except WebDriverException:
            pass


def _enclosing_clickable(browser, element):
    """Return the button/``role=button`` that wraps an icon, or the icon."""
    try:
        wrapped = browser.execute_script(
            "return arguments[0].closest('button') || "
            "arguments[0].closest(\"[role='button']\");",
            element,
        )
    except WebDriverException:
        wrapped = None

    if wrapped:
        try:
            if wrapped.is_displayed():
                return wrapped
        except WebDriverException:
            pass

    return element


def get_links_from_feed(browser, amount, num_of_search, logger):
    """Fetches random number of links from feed and returns a list of links"""

    feeds_link = "https://www.instagram.com/"

    # Check URL of the webpage, if it already is in Feeds page, then do not
    # navigate to it again
    web_address_navigator(browser, feeds_link)

    for i in range(num_of_search + 1):
        browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        update_activity(browser, state=None)
        sleep(2)

    # get links
    link_elems = browser.find_elements(
        By.XPATH, read_xpath(get_links_from_feed.__name__, "get_links")
    )

    total_links = len(link_elems)
    logger.info("Total of links feched for analysis: {}".format(total_links))
    links = []
    try:
        if link_elems:
            links = [link_elem.get_attribute("href") for link_elem in link_elems]
            logger.info("~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            for i, link in enumerate(links):
                print(i, link)
            logger.info("~~~~~~~~~~~~~~~~~~~~~~~~~~~")

    except BaseException as e:
        logger.error("link_elems error \n\t{}".format(str(e).encode("utf-8")))

    return links


def get_main_element(browser, link_elems, skip_top_posts):
    main_elem = None

    if not link_elems:
        main_elem = browser.find_element(
            By.XPATH, read_xpath(get_links_for_location.__name__, "top_elements")
        )
    else:
        if skip_top_posts:
            main_elem = browser.find_element(
                By.XPATH, read_xpath(get_links_for_location.__name__, "main_elem")
            )
        else:
            main_elem = browser.find_element(By.TAG_NAME, "main")

    return main_elem


def get_links_for_location(
    browser, location, amount, logger, media=None, skip_top_posts=True
):
    """
    Fetches the number of links specified by amount and returns a list of links
    """

    if media is None:
        # All known media types
        media = MEDIA_ALL_TYPES
    elif media == MEDIA_PHOTO:
        # Include posts with multiple images in it
        media = [MEDIA_PHOTO, MEDIA_CAROUSEL]
    else:
        # Make it an array to use it in the following part
        media = [media]

    location_link = "https://www.instagram.com/explore/locations/{}".format(location)
    web_address_navigator(browser, location_link)

    top_elements = browser.find_element(
        By.XPATH, read_xpath(get_links_for_location.__name__, "top_elements")
    )
    top_posts = top_elements.find_elements(By.TAG_NAME, "a")
    sleep(1)

    if skip_top_posts:
        main_elem = browser.find_element(
            By.XPATH, read_xpath(get_links_for_location.__name__, "main_elem")
        )
    else:
        main_elem = browser.find_element(By.TAG_NAME, "main")

    link_elems = main_elem.find_elements(By.TAG_NAME, "a")
    sleep(1)

    if not link_elems:  # this location does not have `Top Posts` or it
        # really is empty..
        main_elem = browser.find_element(
            By.XPATH, get_links_for_location.__name__, "top_elements"
        )
        top_posts = []
    sleep(2)

    try:
        possible_posts = browser.execute_script(
            "return window._sharedData.entry_data."
            "LocationsPage[0].graphql.location.edge_location_to_media.count"
        )

    except WebDriverException:
        logger.info(
            "Failed to get the amount of possible posts in '{}' "
            "location".format(location)
        )
        possible_posts = None

    logger.info(
        "desired amount: {}  |  top posts [{}]: {}  |  possible posts: "
        "{}".format(
            amount,
            "enabled" if not skip_top_posts else "disabled",
            len(top_posts),
            possible_posts,
        )
    )

    if possible_posts is not None:
        possible_posts = (
            possible_posts if not skip_top_posts else possible_posts - len(top_posts)
        )
        amount = possible_posts if amount > possible_posts else amount
        # sometimes pages do not have the correct amount of posts as it is
        # written there, it may be cos of some posts is deleted but still
        # keeps counted for the location

    # Get links
    links = get_links(browser, location, logger, media, main_elem)
    filtered_links = len(links)
    try_again = 0
    sc_rolled = 0
    nap = 1.5
    put_sleep = 0
    try:
        while filtered_links in range(1, amount):
            if sc_rolled > 100:
                logger.info("Scrolled too much! ~ sleeping a bit :>")
                sleep(600)
                sc_rolled = 0

            for i in range(3):
                browser.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);"
                )
                update_activity(browser, state=None)
                sc_rolled += 1
                sleep(nap)  # if not slept, and internet speed is low,
                # instagram will only scroll one time, instead of many times
                # you sent scroll command...

            sleep(3)
            links.extend(get_links(browser, location, logger, media, main_elem))

            links_all = links  # uniqify links while preserving order
            s = set()
            links = []
            for i in links_all:
                if i not in s:
                    s.add(i)
                    links.append(i)

            if len(links) == filtered_links:
                try_again += 1
                nap = 3 if try_again == 1 else 5
                logger.info(
                    "Insufficient amount of links ~ trying again: {}".format(try_again)
                )
                sleep(3)

                if try_again > 2:  # you can try again as much as you want
                    # by changing this number
                    if put_sleep < 1 and filtered_links <= 21:
                        logger.info(
                            "Cor! Did you send too many requests?  ~let's rest some"
                        )
                        sleep(600)
                        put_sleep += 1

                        browser.execute_script("location.reload()")
                        update_activity(browser, state=None)
                        try_again = 0
                        sleep(10)

                        main_elem = get_main_element(
                            browser, link_elems, skip_top_posts
                        )
                    else:
                        logger.info(
                            "'{}' location POSSIBLY has less images than "
                            "desired:{} found:{}...".format(
                                location, amount, len(links)
                            )
                        )
                        break
            else:
                filtered_links = len(links)
                try_again = 0
                nap = 1.5
    except Exception:
        raise

    sleep(4)

    return links[:amount]


def get_links_for_tag(browser, tag, amount, skip_top_posts, randomize, media, logger):
    """
    Fetches the number of links specified by amount and returns a list of links
    """
    requested_amount = amount

    if media is None:
        # All known media types
        media = MEDIA_ALL_TYPES
    elif media == MEDIA_PHOTO:
        # Include posts with multiple images in it
        media = [MEDIA_PHOTO, MEDIA_CAROUSEL]
    else:
        # Make it an array to use it in the following part
        media = [media]

    tag = tag[1:] if tag[:1] == "#" else tag

    tag_link = "https://www.instagram.com/explore/tags/{}".format(tag)
    web_address_navigator(browser, tag_link)

    # Newer Instagram redirects hashtag pages to its keyword search page.
    # That layout has a single grid and no separate "Top posts" section.
    on_search_page = "/explore/search/keyword/" in browser.current_url

    if on_search_page:
        main_elem = browser.find_element(By.TAG_NAME, "main")
        top_posts = []
        link_elems = []
        skip_top_posts = False
    else:
        top_elements = _find_elements_fast(
            browser,
            By.XPATH,
            read_xpath(get_links_for_tag.__name__, "top_elements"),
        )
        top_posts = (
            top_elements[0].find_elements(By.TAG_NAME, "a") if top_elements else []
        )
        sleep(1)

        if skip_top_posts:
            main_candidates = _find_elements_fast(
                browser,
                By.XPATH,
                read_xpath(get_links_for_tag.__name__, "main_elem"),
            )
            main_elem = (
                main_candidates[0]
                if main_candidates
                else browser.find_element(By.TAG_NAME, "main")
            )
        else:
            main_elem = browser.find_element(By.TAG_NAME, "main")
        link_elems = main_elem.find_elements(By.TAG_NAME, "a")
        sleep(1)

        if not link_elems:  # this tag does not have `Top Posts` or it really is
            # empty..
            main_elem = browser.find_element(By.TAG_NAME, "main")
            top_posts = []
        sleep(2)

    try:
        possible_posts = browser.execute_script(
            "return window._sharedData.entry_data."
            "TagPage[0].graphql.hashtag.edge_hashtag_to_media.count"
        )

    except WebDriverException:
        # Instagram removed ``window._sharedData``. The old DOM fallback used
        # ``find_elements`` with the implicit page delay and stalled every
        # hashtag for ~25-30 seconds before giving up; the count is optional
        # (it only clamps the requested amount), so skip it.
        possible_posts = None

    if skip_top_posts:
        amount = amount + 9

    logger.info(
        "desired amount: {}  |  top posts [{}]: {}  |  possible posts: "
        "{}".format(
            amount,
            "enabled" if not skip_top_posts else "disabled",
            len(top_posts),
            possible_posts,
        )
    )

    if possible_posts is not None:
        amount = possible_posts if amount > possible_posts else amount
    # sometimes pages do not have the correct amount of posts as it is
    # written there, it may be cos of some posts is deleted but still keeps
    # counted for the tag

    # Get links
    links = get_links(browser, tag, logger, media, main_elem)
    links = _unique_links(links)
    try_again = 0
    sc_rolled = 0
    nap = 1.5
    put_sleep = 0
    try:
        # Keep scrolling until enough links were collected. The old condition
        # (``filtered_links in range(1, amount)``) never entered the loop when
        # ``amount`` was 1, which is the common case for this project: hashtag
        # pages that redirect to the keyword search layout then returned no
        # links at all ("page does not contain a picture").
        while len(links) < amount:
            if sc_rolled > 100:
                logger.info("Scrolled too much! ~ sleeping a bit :>")
                sleep(600)
                sc_rolled = 0

            for i in range(3):
                browser.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);"
                )
                update_activity(browser, state=None)
                sc_rolled += 1
                sleep(nap)  # if not slept, and internet speed is low,
                # instagram will only scroll one time, instead of many times
                # you sent scroll command...

            sleep(3)
            collected = len(links)
            links = _unique_links(
                links + get_links(browser, tag, logger, media, main_elem)
            )

            if len(links) == collected:
                try_again += 1
                nap = 3 if try_again == 1 else 5
                logger.info(
                    "Insufficient amount of links ~ trying again: {}".format(try_again)
                )
                sleep(3)

                if try_again > 2:  # you can try again as much as you want
                    # by changing this number
                    if put_sleep < 1 and 0 < len(links) <= 21:
                        logger.info(
                            "Cor! Did you send too many requests?  ~let's rest some"
                        )
                        sleep(30)
                        put_sleep += 1

                        browser.execute_script("location.reload()")
                        update_activity(browser, state=None)
                        try_again = 0
                        sleep(10)

                        main_elem = browser.find_element(By.TAG_NAME, "main")
                    else:
                        logger.info(
                            "'{}' tag POSSIBLY has less images than "
                            "desired:{} found:{}...".format(tag, amount, len(links))
                        )
                        break
            else:
                try_again = 0
                nap = 1.5
    except Exception:
        raise

    sleep(4)

    if not links:
        logger.info("'{}' page does not contain a picture".format(tag))

    if skip_top_posts and len(links) > 9:
        # The first grid row(s) are the "Top posts" section. Only drop them
        # when enough posts were collected, otherwise a tag with a small grid
        # would lose every candidate it has.
        del links[0:9]

    if randomize is True:
        random.shuffle(links)

    return links[:requested_amount]


def get_links_for_username(
    browser,
    username,
    person,
    amount,
    logger,
    logfolder,
    randomize=False,
    media=None,
    taggedImages=False,
):
    """
    Fetches the number of links specified by amount and returns a list of links
    """

    if media is None:
        # All known media types
        media = MEDIA_ALL_TYPES
    elif media == MEDIA_PHOTO:
        # Include posts with multiple images in it
        media = [MEDIA_PHOTO, MEDIA_CAROUSEL]
    else:
        # Make it an array to use it in the following part
        media = [media]

    logger.info("Getting {} image list...".format(person))

    user_link = "https://www.instagram.com/{}/".format(person)
    if taggedImages:
        user_link = user_link + "tagged/"

    # if private user, we can get links only if we following
    following_status, _ = get_following_status(
        browser, "profile", username, person, None, logger, logfolder
    )

    # Check URL of the webpage, if it already is user's profile page,
    # then do not navigate to it again
    web_address_navigator(browser, user_link)

    if not is_page_available(browser, logger):
        logger.error(
            "Instagram error: The link you followed may be broken, or the "
            "page may have been removed..."
        )
        return False

    # if following_status is None:
    #    browser.wait_for_valid_connection(browser, username, logger)

    # if following_status == 'Follow':
    #    browser.wait_for_valid_authorization(browser, username, logger)

    is_private = is_private_profile(browser, logger, following_status == "Following")

    if (
        is_private is None
        or (is_private is True and following_status not in ["Following", True])
        or (following_status == "Blocked")
    ):
        logger.info(
            "This user is private and we are not following. '{}':'{}'".format(
                is_private, following_status
            )
        )
        return False

    # Get links
    links = []
    main_elem = browser.find_element(By.TAG_NAME, "article")
    posts_count = get_number_of_posts(browser)
    attempt = 0

    if posts_count is not None and amount > posts_count:
        logger.info(
            "You have requested to get {} posts from {}'s profile page but"
            " there only {} posts available :D".format(amount, person, posts_count)
        )
        amount = posts_count

    while len(links) < amount:
        initial_links = links
        browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        # update server calls after a scroll request
        update_activity(browser, state=None)
        sleep(0.66)

        # using `extend`  or `+=` results reference stay alive which affects
        # previous assignment (can use `copy()` for it)
        main_elem = browser.find_element(By.TAG_NAME, "article")
        links = links + get_links(browser, person, logger, media, main_elem)
        links = sorted(set(links), key=links.index)

        if len(links) == len(initial_links):
            if attempt >= 7:
                logger.info(
                    "There are possibly less posts than {} in {}'s profile "
                    "page!".format(amount, person)
                )
                break
            else:
                attempt += 1
        else:
            attempt = 0

    if randomize is True:
        random.shuffle(links)

    return links[:amount]


def get_media_edge_comment_string(media):
    """AB test (Issue 3712) alters the string for media edge, this resolves it"""
    options = ["edge_media_to_comment", "edge_media_preview_comment"]
    for option in options:
        try:
            media[option]
        except KeyError:
            continue
        return option


def _post_shortcode(link):
    """Return the shortcode of a post/reel link, or ``None``."""
    match = re.search(r"/(?:p|reel|tv)/([^/?#]+)", link or "")
    return match.group(1) if match else None


def _unique_links(links):
    """De-duplicate links while preserving their order."""
    seen = set()
    unique = []
    for link in links:
        if link not in seen:
            seen.add(link)
            unique.append(link)

    return unique


def _get_meta_description(browser):
    """Return the page's ``og:description``/``description`` meta content."""
    for element in _find_elements_fast(
        browser,
        By.XPATH,
        "//meta[@property='og:description' or @name='description']",
    ):
        try:
            description = (element.get_attribute("content") or "").strip()
        except WebDriverException:
            description = ""
        if description:
            return description

    return ""


_META_DATE_RE = re.compile(
    r"\bon\s+(?:([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})"
    r"|(\d{1,2})\s+([A-Za-z]+)\s+(\d{4}))"
)


def _parse_meta_date(description):
    """Parse the publish date out of a post's meta description."""
    match = _META_DATE_RE.search(description or "")
    if not match:
        return None

    if match.group(1):
        month, day, year = match.group(1), match.group(2), match.group(3)
        stamp = "{} {}, {}".format(month, day, year)
        date_formats = ("%B %d, %Y", "%b %d, %Y")
    else:
        day, month, year = match.group(4), match.group(5), match.group(6)
        stamp = "{} {} {}".format(day, month, year)
        date_formats = ("%d %B %Y", "%d %b %Y")

    for date_format in date_formats:
        try:
            parsed = datetime.strptime(stamp, date_format)
        except ValueError:
            continue
        return parsed.replace(tzinfo=timezone.utc)

    return None


def _caption_from_meta_description(description):
    """Return the caption part of a post's meta description, if present."""
    match = re.search(
        r"\bon\s+[A-Za-z]+\s+\d{1,2},\s*\d{4}[^:]*:\s*(.*)$",
        description or "",
        re.DOTALL,
    )
    if not match:
        return None

    caption = match.group(1).strip()
    if caption.startswith('"'):
        caption = caption[1:]
    # Instagram closes the quoted caption with ``".`` and may append a
    # right-to-left mark for Persian captions.
    caption = caption.rstrip('".\u200e\u200f \t\r\n')

    return caption or None


def get_post_data_from_page(browser):
    """Read post details from the DOM when the page has no JSON data."""
    description = _get_meta_description(browser)
    if not description:
        return None, None, False

    # The description looks like:
    # '1M likes, 3,346 comments - chrishenry on December 7, 2023: "..."'
    match = re.search(r"-\s+@?([\w.]+)\s+on\s+", description)
    if match is None:
        return None, None, False

    return (
        match.group(1),
        _caption_from_meta_description(description),
        bool(_find_elements_fast(browser, By.TAG_NAME, "video")),
    )


def get_post_datetime(browser):
    """Return the opened post's publish time as an aware UTC datetime.

    The ``og:description`` meta tag contains the post's publish date and is
    the most reliable source. Comments are rendered with their own
    ``<time datetime="...">`` elements too, so the ``<time>`` fallback takes
    the earliest timestamp it finds: comments are always newer than the post
    itself. Returns ``None`` when the date cannot be determined.
    """

    from_meta = _parse_meta_date(_get_meta_description(browser))
    if from_meta is not None:
        return from_meta

    timestamps = []
    for element in _find_elements_fast(browser, By.XPATH, "//time[@datetime]"):
        try:
            value = (element.get_attribute("datetime") or "").strip()
        except WebDriverException:
            continue
        if not value:
            continue
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        timestamps.append(parsed)

    if not timestamps:
        return None

    now = datetime.now(timezone.utc)
    timestamps = [stamp for stamp in timestamps if stamp <= now + timedelta(days=1)]

    return min(timestamps) if timestamps else None


def check_link(
    browser,
    post_link,
    dont_like,
    mandatory_words,
    mandatory_language,
    mandatory_character,
    is_mandatory_character,
    check_character_set,
    ignore_if_contains,
    logger,
    max_post_age_days=None,
):
    """
    Check the given link if it is appropriate

    :param browser: The selenium webdriver instance
    :param post_link:
    :param dont_like: hashtags of inappropriate phrases
    :param mandatory_words: words of appropriate phrases
    :param ignore_if_contains:
    :param logger: the logger instance
    :return: tuple of
        boolean: True if inappropriate,
        string: the username,
        boolean: True if it is video media,
        string: the message if inappropriate else 'None',
        string: set the scope of the return value
    """

    # Check URL of the webpage, if it already is post's page, then do not
    # navigate to it again
    web_address_navigator(browser, post_link, logger)

    # Check if the Post is Valid/Exists
    post_page = get_additional_data(browser)

    if post_page is None:
        # Modern pages no longer ship the old JSON data, so fall back to the
        # metadata Instagram renders into the document.
        user_name, image_text, is_video = get_post_data_from_page(browser)
        if user_name is None:
            # A slow page can render its metadata a moment later; check once
            # more before declaring the post unavailable.
            try:
                browser.refresh()
            except WebDriverException:
                pass
            sleep(2)
            user_name, image_text, is_video = get_post_data_from_page(browser)

        if user_name is None:
            logger.warning("Unavailable Page: {}".format(post_link))
            return True, None, None, "Unavailable Page", "Failure"

        post_page = {
            "items": [
                {
                    "is_unified_video": is_video,
                    "user": {"username": user_name},
                    "caption": {"text": image_text} if image_text else None,
                }
            ]
        }

    # Gets the description of the post's link and checks for the dont_like tags
    graphql = "graphql" in post_page
    location_name = None

    if graphql:
        media = post_page["graphql"]["shortcode_media"]
        is_video = media["is_video"]
        user_name = media["owner"]["username"]
        image_text = media["edge_media_to_caption"]["edges"]
        image_text = image_text[0]["node"]["text"] if image_text else None
        location = media["location"]
        location_name = location["name"] if location else None
        media_edge_string = get_media_edge_comment_string(media)
        # Gets all comments on media
        comments = (
            media[media_edge_string]["edges"]
            if media[media_edge_string]["edges"]
            else None
        )
        owner_comments = ""
        # Concat all owner comments
        if comments is not None:
            for comment in comments:
                if comment["node"]["owner"]["username"] == user_name:
                    owner_comments = owner_comments + "\n" + comment["node"]["text"]

    else:
        media = post_page ['items'] [0]
        is_video = media ["is_unified_video"]
        user_name = media ["user"] ["username"]
        image_text = None
        if media["caption"]:
            image_text = media ["caption"] ["text"]
        # RC: Disabling owner's comments temporarily
        owner_comments = ""

    if owner_comments == "":
        owner_comments = None

    # Append owner comments to description as it might contain further tags
    if image_text is None:
        image_text = owner_comments

    elif owner_comments:
        image_text = image_text + "\n" + owner_comments

    # RC: Dropping this temporarily
    # If the image still has no description gets the first comment
    # if image_text is None:
    #     if graphql:
    #         media_edge_string = get_media_edge_comment_string(media)
    #         image_text = media[media_edge_string]["edges"]
    #         image_text = image_text[0]["node"]["text"] if image_text else None

    #     else:
    #         image_text = media["comments"]["nodes"]
    #         image_text = image_text[0]["text"] if image_text else None

    if image_text is None:
        image_text = "No description"

    logger.info("Image from: {}".format(user_name))
    logger.info("Image link: {}".format(post_link))
    logger.info("Description: {}".format(image_text))

    # Only interact with accounts that are currently active: the post itself
    # must have been published within the allowed age. A recent post proves
    # the author is still posting, so old posts are skipped entirely.
    if max_post_age_days:
        post_datetime = get_post_datetime(browser)
        if post_datetime is None:
            logger.info(
                "--> Skipping '{}': the post date is unavailable, so the "
                "account's activity cannot be verified".format(user_name)
            )
            return (
                True,
                user_name,
                is_video,
                "Post date unavailable",
                "Inactive account",
            )

        max_age = timedelta(days=max_post_age_days)
        age = datetime.now(timezone.utc) - post_datetime
        if age > max_age:
            logger.info(
                "--> Skipping '{}': the post is {} days old, but only posts "
                "from the last {} days are eligible".format(
                    user_name, max(age.days, 0), max_post_age_days
                )
            )
            return (
                True,
                user_name,
                is_video,
                "Post is too old",
                "Inactive account",
            )

        logger.info(
            "--> Post from '{}' is {} days old; activity check passed".format(
                user_name, max(age.days, 0)
            )
        )

    # Check if mandatory character set, before adding the location to the text
    if mandatory_language:
        if not check_character_set(image_text):
            return (
                True,
                user_name,
                is_video,
                "Mandatory language not fulfilled",
                "Not mandatory language",
            )

    # Append location to image_text so we can search through both in one go
    if location_name:
        logger.info("Location: {}".format(location_name))
        image_text = image_text + "\n" + location_name

    if mandatory_words:
        if not evaluate_mandatory_words(image_text, mandatory_words):
            return (
                True,
                user_name,
                is_video,
                "Mandatory words not fulfilled",
                "Not mandatory likes",
            )

    image_text_lower = image_text.lower()
    ignore_if_contains_lower = [x.lower() for x in ignore_if_contains]
    if any((word in image_text_lower for word in ignore_if_contains_lower)):
        return False, user_name, is_video, "None", "Pass"

    dont_like_regex = []

    for dont_likes in dont_like:
        if dont_likes.startswith("#"):
            dont_like_regex.append(dont_likes + r"([^\d\w]|$)")
        elif dont_likes.startswith("["):
            dont_like_regex.append("#" + dont_likes[1:] + r"[\d\w]+([^\d\w]|$)")
        elif dont_likes.startswith("]"):
            dont_like_regex.append(r"#[\d\w]+" + dont_likes[1:] + r"([^\d\w]|$)")
        else:
            dont_like_regex.append(r"#[\d\w]*" + dont_likes + r"[\d\w]*([^\d\w]|$)")

    for dont_likes_regex in dont_like_regex:
        quash = re.search(dont_likes_regex, image_text, re.IGNORECASE)
        if quash:
            quashed = (
                (((quash.group(0)).split("#")[1]).split(" ")[0])
                .split("\n")[0]
                .encode("utf-8")
            )  # dismiss possible space and newlines
            iffy = (
                (re.split(r"\W+", dont_likes_regex))[3]
                if dont_likes_regex.endswith("*([^\\d\\w]|$)")
                else (re.split(r"\W+", dont_likes_regex))[1]  # 'word' without format
                if dont_likes_regex.endswith("+([^\\d\\w]|$)")
                else (re.split(r"\W+", dont_likes_regex))[3]  # '[word'
                if dont_likes_regex.startswith("#[\\d\\w]+")
                else (re.split(r"\W+", dont_likes_regex))[1]  # ']word'
            )  # '#word'
            inapp_unit = 'Inappropriate! ~ contains "{}"'.format(
                quashed if iffy == quashed else '" in "'.join([str(iffy), str(quashed)])
            )
            return True, user_name, is_video, inapp_unit, "Undesired word"

    return False, user_name, is_video, "None", "Success"


def like_image(browser, username, blacklist, logger, logfolder, total_liked_img):
    """Likes the browser opened image"""
    # check action availability
    if quota_supervisor("likes") == "jump":
        return False, "jumped"

    media = "Image"  # by default
    like_xpath = read_xpath(like_image.__name__, "like")
    unlike_xpath = read_xpath(like_image.__name__, "unlike")
    play_xpath = read_xpath(like_image.__name__, "play")

    play_elem = _find_elements_fast(browser, By.XPATH, play_xpath)
    if len(play_elem) == 1:
        # This is because now IG is not only Images, User can share Images and
        # Videos in one post at the same time, it could be Image -> Video or
        # Video -> Image so we will try to Like the post like one object.
        media = "Video"
        comment = read_xpath(open_comment_section.__name__, "comment_elem")
        comment_elem = _find_elements_fast(browser, By.XPATH, comment)

        # Now, move until 'Comment' section to determine the status of post
        # Notice that some videos comes from TikTok and could have larger size
        # c'est la vie...
        logger.info("--> Found 'Play' button for a video, trying to like it")
        if comment_elem:
            browser.execute_script(
                "arguments[0].scrollIntoView(true);", comment_elem[0]
            )

    # find first for like element
    like_elem = _find_elements_fast(browser, By.XPATH, like_xpath)

    # Comment like buttons share the same `aria-label`. Keep only the post's
    # like button. Checking `closest('ul')` in JS avoids one 25s implicit-wait
    # timeout per comment icon.
    post_like_elems = []
    for element in like_elem:
        try:
            if not element.is_displayed():
                continue
            in_comment = browser.execute_script(
                "return arguments[0].closest('ul') !== null;", element
            )
        except WebDriverException:
            continue
        if not in_comment:
            post_like_elems.append(element)
    if post_like_elems:
        like_elem = post_like_elems

    if len(like_elem) >= 1:
        # sleep real quick right before clicking the element
        sleep(2)
        logger.info("--> {}...".format(media))

        target = _enclosing_clickable(browser, like_elem[0])
        click_element(browser, target)

        # Give the page a moment to switch the icon from "Like" to "Unlike".
        liked_elem = []
        for _ in range(10):
            liked_elem = _find_elements_fast(browser, By.XPATH, unlike_xpath)
            if liked_elem:
                break
            sleep(1)

        if len(liked_elem) >= 1:
            logger.info("--> {} liked!".format(media))
            Event().liked(username)
            update_activity(
                browser, action="likes", state=None, logfolder=logfolder, logger=logger
            )

            if blacklist["enabled"] is True:
                action = "liked"
                add_user_to_blacklist(
                    username, blacklist["campaign"], action, logger, logfolder
                )

            # get the post-like delay time to sleep
            naply = get_action_delay("like")
            sleep(naply)

            # after liking an image we do check if liking activity was blocked
            if not verify_liked_image(browser, logger):
                return False, "block on likes"

            return True, "success"

        else:
            # Maybe the DOM was just slow, or the click landed on the wrapper.
            # Re-check once more before declaring the post unlikable.
            sleep(15)
            if _find_elements_fast(browser, By.XPATH, unlike_xpath):
                logger.info("--> {} liked!".format(media))
                Event().liked(username)
                update_activity(
                    browser,
                    action="likes",
                    state=None,
                    logfolder=logfolder,
                    logger=logger,
                )
                naply = get_action_delay("like")
                sleep(naply)
                return True, "success"

            logger.info(
                "--> {} was not able to get liked! maybe blocked?".format(media)
            )

    else:
        liked_elem = _find_elements_fast(browser, By.XPATH, unlike_xpath)
        if len(liked_elem) >= 1:
            logger.info("--> {} already liked!".format(media))
            return False, "already liked"

    logger.info("--> Invalid Like Element!")

    return False, "invalid element"


def verify_liked_image(browser, logger):
    """Check for a ban on likes using the last liked image"""

    browser.refresh()
    unlike_xpath = read_xpath(like_image.__name__, "unlike")

    # The refreshed page can take a moment to render the post's action bar.
    for _ in range(8):
        if _find_elements_fast(browser, By.XPATH, unlike_xpath):
            return True
        sleep(1)

    logger.warning("--> Image was NOT liked! You have a BLOCK on likes!")
    return False


def get_tags(browser, url):
    """Gets all the tags of the given description in the url"""

    # Check URL of the webpage, if it already is the one to be navigated,
    # then do not navigate to it again
    web_address_navigator(browser, url)

    additional_data = get_additional_data(browser)
    if not additional_data:
        return []

    try:
        image_text = additional_data["graphql"]["shortcode_media"][
            "edge_media_to_caption"
        ]["edges"][0]["node"]["text"]
    except (KeyError, IndexError, TypeError):
        return []

    if not image_text:
        image_text = ""

    tags = findall(r"#\w*", image_text)

    return tags


def get_links(browser, page, logger, media, element):
    links = []

    try:
        # Collect the links and their media type in a single browser call.
        # Reading every grid item through WebDriver is very slow on current
        # Firefox/Instagram layouts.
        posts = browser.execute_script(
            """
            return Array.from(document.querySelectorAll('a[href^="/p/"]'))
                .map(function (anchor) {
                    const labels = Array.from(
                        anchor.querySelectorAll('svg[aria-label]')
                    ).map(function (icon) {
                        return icon.getAttribute('aria-label');
                    });
                    return {
                        href: anchor.href,
                        labels: labels,
                        has_video: anchor.querySelector('video') !== null
                    };
                });
            """
        )
        sleep(random.randint(2, 5))

        if not posts:
            return links

        for post in posts:
            post_href = post.get("href")
            labels = post.get("labels") or []

            if "Reel" in labels or "Clip" in labels:
                post_category = MEDIA_CLIP
            elif "Carousel" in labels:
                post_category = MEDIA_CAROUSEL
            elif "Video" in labels or "IGTV" in labels or post.get("has_video"):
                post_category = MEDIA_VIDEO
            else:
                post_category = MEDIA_PHOTO

            logger.info("Found media type: {}".format(post_category))

            if post_category in media:
                links.append(post_href)

    except WebDriverException as e:
        logger.error("link_elems error \n\t{}".format(str(e)))

    # This block is intended to provide more information to the InstaPy user, they would like to
    # know why the Links cannot be "[Un]Liked", I would like to say that first check if the Media
    # Type is new, second check if the xpath has been updated and finally verify the acct is not
    # under a cold-down stage.
    # If the user can use the link outside InstaPy, they would know IG targeted the acct as
    # automated.
    for i, link in enumerate(links):
        logger.info("Links retrieved:: [{}/{}]".format(i + 1, link))

    return links


def verify_liking(browser, maximum, minimum, logger):
    """Get the amount of existing existing likes and compare it against maximum
    & minimum values defined by user"""

    post_page = get_additional_data(browser)
    if not post_page:
        # The post data is not available, so the like count cannot be checked.
        return True

    try:
        if "graphql" in post_page:
            likes_count = (
                post_page["graphql"]["shortcode_media"]
                .get("edge_liked_by", {})
                .get("count", 0)
            )
        else:
            likes_count = post_page["items"][0]["like_count"]
    except (KeyError, IndexError, TypeError):
        return True

    if not likes_count:
        likes_count = 0

    if maximum is not None and likes_count > maximum:
        logger.info(
            "Not liked this post! ~more likes exist off maximum limit at "
            "{}".format(likes_count)
        )
        return False
    elif minimum is not None and likes_count < minimum:
        logger.info(
            "Not liked this post! ~less likes exist off minimum limit "
            "at {}".format(likes_count)
        )
        return False

    return True


def like_comment(browser, original_comment_text, logger):
    """Like the given comment"""
    comments_block_XPath = read_xpath(
        like_comment.__name__, "comments_block"
    )  # quite an efficient
    # location path

    try:
        comments_block = browser.find_elements(By.XPATH, comments_block_XPath)
        for comment_line in comments_block:
            comment_elem = comment_line.find_elements(By.TAG_NAME, "span")[0]
            comment = extract_text_from_element(comment_elem)

            if comment and (comment == original_comment_text):
                # find "Like" span (a direct child of Like button)
                span_like_elements = comment_line.find_elements(
                    By.XPATH, read_xpath(like_comment.__name__, "span_like_elements")
                )
                if not span_like_elements:
                    # this is most likely a liked comment
                    return True, "success"

                # like the given comment
                span_like = span_like_elements[0]
                comment_like_button = span_like.find_element(
                    By.XPATH, read_xpath(like_comment.__name__, "comment_like_button")
                )
                click_element(browser, comment_like_button)

                # verify if like succeeded by waiting until the like button
                # element goes stale..
                button_change = explicit_wait(
                    browser, "SO", [comment_like_button], logger, 7, False
                )

                if button_change:
                    logger.info("--> Liked the comment!")
                    sleep(random.uniform(1, 2))
                    return True, "success"

                else:
                    logger.info("--> Unfortunately, comment was not liked.")
                    sleep(random.uniform(0, 1))
                    return False, "failure"

    except (NoSuchElementException, StaleElementReferenceException) as exc:
        logger.error(
            "Error occurred while liking a comment.\n\t{}".format(
                str(exc).encode("utf-8")
            )
        )
        return False, "error"

    return None, "unknown"
