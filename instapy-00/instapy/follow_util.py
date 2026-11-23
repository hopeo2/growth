""" Module which handles the follow features """
# import built-in & third-party modules
from random import randint
from time import sleep

# import exceptions
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By

# import InstaPy modules
from .util import (
    get_username_from_id,
    is_page_available,
    load_user_id,
    update_activity,
    web_address_navigator,
)
from .xpath import read_xpath


def _find_elements_fast(browser, by, value):
    """``find_elements`` without the long implicit wait (25s by default)."""
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


def get_following_status(
    browser, track, username, person, person_id, logger, logfolder
):
    """Verify if you are following the user in the loaded page"""
    if person == username:
        return "OWNER", None

    if track == "profile":
        ig_homepage = "https://www.instagram.com/"
        web_address_navigator(browser, ig_homepage + person)

    failure_msg = "--> Unable to detect the following status of '{}'!"
    user_inaccessible_msg = (
        "Couldn't access the profile page of '{}'!\t~might have changed the"
        " username".format(person)
    )

    # check if the page is available
    valid_page = is_page_available(browser, logger)
    if not valid_page:
        logger.warning(user_inaccessible_msg)
        person_new = verify_username_by_id(
            browser, username, person, None, logger, logfolder
        )
        if person_new:
            ig_homepage = "https://www.instagram.com/"
            web_address_navigator(browser, ig_homepage + person_new)
            valid_page = is_page_available(browser, logger)
            if not valid_page:
                logger.warning(failure_msg.format(person_new))
                return "UNAVAILABLE", None
        else:
            logger.warning(failure_msg.format(person))
            return "UNAVAILABLE", None

    # wait until the follow button is located and visible, then get it
    following_status, follow_button = find_visible_follow_button(browser)

    if follow_button is None:
        # The page may still be rendering; poll briefly.
        for _ in range(6):
            sleep(2)
            following_status, follow_button = find_visible_follow_button(browser)
            if follow_button is not None:
                break

    if follow_button is None:
        browser.execute_script("location.reload()")
        update_activity(browser, state=None)
        sleep(randint(2, 5))

        following_status, follow_button = find_visible_follow_button(browser)
        if follow_button is None:
            # cannot find any of the expected buttons
            logger.error(failure_msg.format(person))
            return "UNAVAILABLE", None

    return following_status, follow_button


FOLLOW_LABELS = ("Follow", "Follow Back", "Following", "Requested", "Unblock")
# When several labels exist in the same scope, prefer the one that describes
# the account's action button over the alternative shown for hover states.
FOLLOW_LABEL_PRIORITY = ("Follow", "Follow Back", "Following", "Requested", "Unblock")


def find_visible_follow_button(browser):
    """Return ``(label, element)`` for the visible follow button, or (None, None).

    Instagram's button text is split across visible and hidden children (the
    hidden part is the chevron icon accessibility text), so XPath text matching
    is unreliable. Selenium's ``element.text`` returns only the visible label.
    """
    for scope_key in (
        "follow_buttons_header",
        "follow_buttons_main",
        "follow_buttons_any",
    ):
        candidates = _find_elements_fast(
            browser,
            By.XPATH,
            read_xpath(get_following_status.__name__, scope_key),
        )

        matches = []
        for element in candidates:
            try:
                if not element.is_displayed():
                    continue
                label = (element.text or "").strip()
                if label not in FOLLOW_LABELS:
                    # Some layouts keep the label only in `aria-label`.
                    aria_label = (element.get_attribute("aria-label") or "").strip()
                    if aria_label in FOLLOW_LABELS:
                        label = aria_label
                if label in FOLLOW_LABELS:
                    matches.append((label, element))
            except WebDriverException:
                continue

        if matches:
            for preferred in FOLLOW_LABEL_PRIORITY:
                chosen = next(
                    (match for match in matches if match[0] == preferred), None
                )
                if chosen is not None:
                    return chosen
            return matches[0]

    return None, None


def verify_username_by_id(browser, username, person, person_id, logger, logfolder):
    """Check if the given user has changed username after the time of
    followed"""

    # try to find the user by ID
    person_id = load_user_id(username, person, logger, logfolder)

    # if person_id is None, inform the InstaPy user that record does not exist
    if person_id not in [None, "unknown", "undefined"]:
        # get the [new] username of the user from the stored user ID
        person_new = get_username_from_id(browser, person_id, logger)

        # if person_new is None, inform the InstaPy user that record does not exist
        if person_new is not None and person_new != person:
            logger.info(
                "User '{}' has changed username and now is called '{}' :S".format(
                    person, person_new
                )
            )
            return person_new

    # check who call this def, since will receive a None value
    logger.info("User '{}' doesn't exist in local records".format(person))
    return None
