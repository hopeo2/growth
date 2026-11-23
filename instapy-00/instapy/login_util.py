"""Module only used for the login part of the script"""
# import built-in & third-party modules
import ipaddress
import json
import os
import pickle
import random
import shutil
import socket
import time

# import exceptions
from selenium.common.exceptions import (
    NoSuchElementException,
    WebDriverException,
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# import InstaPy modules
from .exceptions import InstaPyError
from .time_util import sleep
from .util import (
    check_authorization,
    click_element,
    explicit_wait,
    reload_webpage,
    update_activity,
    web_address_navigator,
)
from .xpath import read_xpath


def bypass_suspicious_login(
    browser, logger, logfolder, bypass_security_challenge_using
):
    """Bypass suspicious loggin attempt verification."""

    # close sign up Instagram modal if available
    dismiss_get_app_offer(browser, logger)
    dismiss_notification_offer(browser, logger)
    dismiss_this_was_me(browser)

    option = None
    if bypass_security_challenge_using == "sms":
        try:
            option = browser.find_element(
                By.XPATH,
                read_xpath(bypass_suspicious_login.__name__, "bypass_with_sms_option"),
            )
        except NoSuchElementException:
            logger.warning(
                "Unable to choose ({}) option to bypass the challenge".format(
                    bypass_security_challenge_using.upper()
                )
            )

    if bypass_security_challenge_using == "email":
        try:
            option = browser.find_element(
                By.XPATH,
                read_xpath(
                    bypass_suspicious_login.__name__, "bypass_with_email_option"
                ),
            )
        except NoSuchElementException:
            logger.warning(
                "Unable to choose ({}) option to bypass the challenge".format(
                    bypass_security_challenge_using.upper()
                )
            )

    # click on your option
    (ActionChains(browser).move_to_element(option).click().perform())
    # next button click will miss the DOM reference for this element, so ->
    option_text = option.text

    # click on security code
    send_security_code_button = browser.find_element(
        By.XPATH,
        read_xpath(bypass_suspicious_login.__name__, "send_security_code_button"),
    )
    (ActionChains(browser).move_to_element(send_security_code_button).click().perform())

    # update server calls
    update_activity(browser, state=None)

    logger.info("Instagram detected an unusual login attempt")
    logger.info('Check Instagram App for "Suspicious Login attempt" prompt')
    logger.info("A security code was sent to your {}".format(option_text))

    security_code = None
    try:
        path = "{}state.json".format(logfolder)
        data = {}
        # check if file exists and has content
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            # load JSON file
            with open(path, "r") as json_file:
                data = json.load(json_file)

        # update connection state
        security_code = data["challenge"]["security_code"]
    except Exception:
        logger.info("Security Code not present in {}state.json file".format(logfolder))

    if security_code is None:
        security_code = input("Type the security code here: ")

    security_code_field = browser.find_element(
        By.XPATH, read_xpath(bypass_suspicious_login.__name__, "security_code_field")
    )

    (
        ActionChains(browser)
        .move_to_element(security_code_field)
        .click()
        .send_keys(security_code)
        .perform()
    )

    # update server calls for both 'click' and 'send_keys' actions
    for _ in range(2):
        update_activity(browser, state=None)

    submit_security_code_button = browser.find_element(
        By.XPATH,
        read_xpath(bypass_suspicious_login.__name__, "submit_security_code_button"),
    )

    (
        ActionChains(browser)
        .move_to_element(submit_security_code_button)
        .click()
        .perform()
    )

    # update server calls
    update_activity(browser, state=None)

    try:
        sleep(3)
        # locate wrong security code message
        wrong_login = browser.find_element(
            By.XPATH, read_xpath(bypass_suspicious_login.__name__, "wrong_login")
        )

        if wrong_login is not None:
            wrong_login_msg = "Wrong security code! Please check the code Instagram sent you and try again."
            update_activity(
                browser,
                action=None,
                state=wrong_login_msg,
                logfolder=logfolder,
                logger=logger,
            )
            logger.warning(wrong_login_msg)

    except NoSuchElementException:
        # correct security code
        pass


IP_ENDPOINTS = (
    "https://ifconfig.co/ip",
    "https://api.ipify.org",
    "https://icanhazip.com",
    "https://checkip.amazonaws.com",
)


def _get_page_text(browser, url):
    """Navigate to ``url`` and return the visible text of its body."""
    browser.get(url)
    return browser.find_element(By.TAG_NAME, "body").text.strip()


def get_ip_info(browser):
    """Return normalized public IP information from a working service.

    Plain-text endpoints are used instead of JSON ones because modern Firefox
    renders JSON responses in its built-in JSON viewer, and ``view-source:``
    navigation is no longer allowed through WebDriver.
    """
    last_error = None
    ip = None

    for endpoint in IP_ENDPOINTS:
        try:
            candidate = _get_page_text(browser, endpoint).split()[0]
            # Make sure we really got an IP and not an HTML error page
            ipaddress.ip_address(candidate)
            ip = candidate
            break
        except Exception as exc:  # try the next provider
            last_error = exc
            continue

    if ip is None:
        raise RuntimeError(
            "Unable to determine the public IP address: {}".format(last_error)
        )

    country_name = "unknown"
    country_code = "unknown"
    try:
        country_name = _get_page_text(browser, "https://ifconfig.co/country")
    except Exception:
        pass
    try:
        country_code = _get_page_text(browser, "https://ifconfig.co/country-iso")
    except Exception:
        pass

    return {
        "ip": ip,
        "country_name": country_name or "unknown",
        "country_code": country_code or "unknown",
    }


def check_browser(browser, logfolder, logger, proxy_address):
    # set initial state to offline
    update_activity(
        browser,
        action=None,
        state="trying to connect",
        logfolder=logfolder,
        logger=logger,
    )

    # check connection status
    try:
        logger.info("-- Connection Checklist [1/2] (Internet Connection Status)")
        current_ip_info = get_ip_info(browser)
        if (
            proxy_address is not None
            and socket.gethostbyname(proxy_address) != current_ip_info["ip"]
        ):
            logger.warning("- Proxy is set, but it's not working properly")
            logger.warning(
                '- Expected Proxy IP is "{}", and the current IP is "{}"'.format(
                    proxy_address, current_ip_info["ip"]
                )
            )
            logger.warning("- Try again or disable the Proxy Address on your setup")
            logger.warning("- Aborting connection...")
            return False
        else:
            logger.info("- Internet Connection Status: ok")
            logger.info(
                '- Current IP is "{}" and it\'s from "{}/{}"'.format(
                    current_ip_info["ip"],
                    current_ip_info["country_name"],
                    current_ip_info["country_code"],
                )
            )
            update_activity(
                browser,
                action=None,
                state="Internet connection is ok",
                logfolder=logfolder,
                logger=logger,
            )
    except Exception:
        logger.warning("- Internet Connection Status: error")
        update_activity(
            browser,
            action=None,
            state="There is an issue with the internet connection",
            logfolder=logfolder,
            logger=logger,
        )
        return False

    # check if hide-selenium extension is running
    logger.info("-- Connection Checklist [2/2] (Hide Selenium Extension)")
    webdriver = browser.execute_script("return window.navigator.webdriver")
    logger.info("- window.navigator.webdriver response: {}".format(webdriver))
    if webdriver:
        logger.warning("- Hide Selenium Extension: error")
    else:
        logger.info("- Hide Selenium Extension: ok")

    # everything is ok, then continue(True)
    return True


# Wording used by Instagram for actual login failures. Plain ``role="alert"``
# regions are also used for harmless progress messages (e.g. "Input Code is
# being validated."), so their text must be checked against these markers.
LOGIN_ERROR_MARKERS = (
    "incorrect",
    "wrong",
    "invalid",
    "not valid",
    "try again",
    "please wait",
    "couldn't find",
    "could not find",
    "doesn't match",
    "has been disabled",
    "suspended",
)


def _find_login_error(browser):
    """Return the first real login error message, if there is one.

    Instagram keeps empty ``role="alert"`` live regions on the page and also
    reuses them for progress messages during verification, so matching on the
    attribute alone is not enough.
    """
    try:
        candidates = browser.find_elements(
            By.XPATH, read_xpath(login_user.__name__, "error_alert")
        )
    except WebDriverException:
        return None

    for candidate in candidates:
        try:
            text = candidate.text.strip()
            if not text:
                continue

            if candidate.get_attribute("id") == "slfErrorAlert":
                return candidate

            if any(marker in text.lower() for marker in LOGIN_ERROR_MARKERS):
                return candidate
        except WebDriverException:
            continue

    return None


# Text shown while Instagram asks the user to enter a code sent to their
# email. These pages are intermediate: the login is neither done nor failed
# until the code has been accepted.
MANUAL_VERIFICATION_MARKERS = (
    "check your email",
    "enter the code",
    "we sent a code",
    "confirm it's you",
    "confirm it’s you",
)


def _needs_manual_verification(browser):
    """Return True when Instagram waits for a code the user has to enter."""
    try:
        page_text = browser.find_element(By.TAG_NAME, "body").text.lower()
    except WebDriverException:
        return False

    return any(marker in page_text for marker in MANUAL_VERIFICATION_MARKERS)


def _login_field_value(browser, xpath):
    """Return the current value of a login field, or None if it is gone."""
    try:
        return browser.find_element(By.XPATH, xpath).get_attribute("value")
    except WebDriverException:
        return None


def fill_login_field(browser, xpath, value, logger, attempts=3):
    """Fill a login field and verify that the entered text was kept.

    Instagram renders the login form on the server and then hydrates it with
    React. Keystrokes sent before hydration finishes can be wiped when React
    takes over the field, which leaves the field empty and makes the form
    submit nothing at all.
    """
    for attempt in range(1, attempts + 1):
        try:
            field = browser.find_element(By.XPATH, xpath)
            field.clear()
            (
                ActionChains(browser)
                .move_to_element(field)
                .click()
                .send_keys(value)
                .perform()
            )
            if field.get_attribute("value") == value:
                return True
        except WebDriverException:
            pass

        if attempt < attempts:
            logger.info("- Login field was reset during page load, retrying...")
            sleep(1)

    return False


def _login_outcome_visible(browser):
    """Return True once Instagram shows a definite login result."""
    try:
        current_url = browser.current_url
    except WebDriverException:
        return True

    # A code prompt is not a final result; wait until the code is accepted
    # (or rejected) before handing control back to the caller.
    if _needs_manual_verification(browser):
        return False

    if "two_factor" in current_url or "/accounts/onetap" in current_url:
        return True

    if "/challenge" in current_url:
        # Only stop here for challenges InstaPy knows how to handle. Other
        # challenge screens (e.g. "Confirm it's you") are completed by the
        # user in the browser, so keep waiting for the final redirect.
        try:
            page_text = browser.find_element(By.TAG_NAME, "body").text.lower()
        except WebDriverException:
            return False

        return any(
            marker in page_text
            for marker in (
                "suspicious login attempt",
                "add your phone number",
                "your account has been disabled",
            )
        )

    if _find_login_error(browser) is not None:
        return True

    try:
        if browser.find_elements(By.XPATH, read_xpath(login_user.__name__, "nav")):
            return True
    except WebDriverException:
        pass

    return False


def wait_for_login_outcome(browser, logger, timeout=300):
    """Wait until the login request has produced a visible outcome.

    Instagram validates the credentials asynchronously, so the URL can stay
    on the login page while the request is in flight. Checking for success
    right after a fixed sleep marks slow (but valid) logins as failures.

    When Instagram asks for a code sent to the user's email, the wait keeps
    going until the code is entered in the browser window.

    Returns True as soon as the logged-in navigation, an error message, or a
    challenge/two-factor page is visible.
    """
    logger.info("- Waiting for Instagram to process the login...")
    deadline = time.monotonic() + timeout
    notice_shown = False

    while time.monotonic() < deadline:
        if _login_outcome_visible(browser):
            return True

        if not notice_shown and _needs_manual_verification(browser):
            notice_shown = True
            logger.info(
                "- Instagram requires a verification code. Enter the code in "
                "the browser window; waiting up to {} seconds...".format(timeout)
            )

        sleep(1)

    logger.warning(
        "- Instagram did not confirm the login within {} seconds".format(timeout)
    )
    return False


def login_user(
    browser,
    username,
    password,
    logger,
    logfolder,
    proxy_address,
    security_code_to_phone,
    security_codes,
    want_check_browser,
):
    """Logins the user with the given username and password"""
    if not username:
        raise InstaPyError(
            "Username not provided. Pass it to InstaPy(username=...) or set "
            "the INSTA_USER environment variable."
        )

    # The cookie file, when present, is enough to restore a session. Only
    # require a password when there is no saved session to fall back on.
    cookie_file = "{0}{1}_cookie.pkl".format(logfolder, username)

    # Reuse a session saved by an older/other workspace instead of forcing a
    # new password login.
    if not os.path.isfile(cookie_file):
        legacy_cookie = os.path.join(
            os.path.expanduser("~"),
            "InstaPy",
            "logs",
            username,
            "{}_cookie.pkl".format(username),
        )
        if os.path.isfile(legacy_cookie):
            try:
                shutil.copy2(legacy_cookie, cookie_file)
                logger.info(
                    "- Imported saved session from '{}'...".format(legacy_cookie)
                )
            except OSError:
                pass

    has_saved_session = os.path.isfile(cookie_file)

    if not password and not has_saved_session:
        raise InstaPyError(
            "Password not provided and no saved session was found for "
            "'{}'. Pass it to InstaPy(password=...) or set the INSTA_PW "
            "environment variable.".format(username)
        )

    # Hotfix - this check crashes more often than not -- plus in not necessary,
    # I can verify my own connection
    if want_check_browser:
        if not check_browser(browser, logfolder, logger, proxy_address):
            return False

    ig_homepage = "https://www.instagram.com"
    web_address_navigator(browser, ig_homepage)

    cookie_loaded = None
    login_state = None

    # try to load cookie from username
    try:
        for cookie in pickle.load(open(cookie_file, "rb")):
            # SameSite = Strict, your cookie will only be sent in a
            # first-party context. In user terms, the cookie will only be sent
            # if the site for the cookie matches the site currently shown in
            # the browser's URL bar.
            if "sameSite" in cookie and cookie["sameSite"] == "None":
                cookie["sameSite"] = "Strict"

            browser.add_cookie(cookie)

        sleep(4)
        cookie_loaded = True
        logger.info("- Cookie file for user '{}' loaded...".format(username))

        # force refresh after cookie load or check_authorization() will FAIL
        reload_webpage(browser)
        sleep(4)

        # cookie has been LOADED, so the user SHOULD be logged in
        login_state = check_authorization(
            browser, username, "activity counts", logger, False
        )
        sleep(4)

    except (WebDriverException, OSError, IOError):
        # Just info the user, not an error
        logger.info("- Cookie file not found, creating cookie...")

    if login_state and cookie_loaded:
        # Cookie loaded and joined IG, dismiss following features if availables
        dismiss_notification_offer(browser, logger)
        dismiss_save_information(browser, logger)
        accept_igcookie_dialogue(browser, logger)
        return True

    # This fix comes from comment in #6060 If not necessary we can remove it
    accept_igcookie_dialogue(browser, logger)

    # if user is still not logged in, then there is an issue with the cookie
    # so go create a new cookie.
    if cookie_loaded:
        if not password:
            raise InstaPyError(
                "The saved session for '{}' is no longer valid. Run once with "
                "INSTA_PW / --password to log in again.".format(username)
            )

        logger.warning(
            "- Issue with cookie for user '{}'. Creating new cookie...".format(username)
        )

        # Error could be faced due to "<button class="sqdOP L3NKy y3zKF"
        # type="button"> Cookie could not be loaded" or similar.
        # Session displayed we are in, but then a failure for the first
        # `login_elem` like the element is no longer attached to the DOM.
        # Saw this issue when session hasn't been used for a while; which means
        # "expiry" values in cookie are outdated.
        try:
            # Since having issues with the cookie a new one can be generated,
            # if cookie cannot be created or deleted stop execution.
            logger.info("- Deleting browser cookies...")
            browser.delete_all_cookies()
            browser.refresh()
            # Delete file from Filesystem if any issue with the cookie
            os.remove(cookie_file)
            sleep(random.randint(3, 5))

        except Exception as e:
            # NF: start
            if isinstance(e, WebDriverException):
                logger.exception(
                    "Error occurred while deleting cookies from web browser!\n\t{}".format(
                        str(e).encode("utf-8")
                    )
                )
            return False
            # NF: end

    web_address_navigator(browser, ig_homepage)

    # The cookie consent modal can cover the login form and swallow clicks
    # and keystrokes, so dismiss it before interacting with the form.
    accept_igcookie_dialogue(browser, logger)

    # Some layouts show the login form directly while others show a "Log In"
    # entry button first. Give the form a moment to render before falling
    # back to the A/B layouts, then click the first *visible* entry button.
    input_username_XP = read_xpath(login_user.__name__, "input_username_XP")
    login_elem = None

    if not explicit_wait(
        browser, "VOEL", [input_username_XP, "XPath"], logger, 10, False
    ):
        logger.warning("Login A/B test detected! Trying another string...")

        for xpath_name in (
            "login_elem",
            "login_elem_no_such_exception",
            "login_elem_no_such_exception_2",
        ):
            try:
                candidates = browser.find_elements(
                    By.XPATH, read_xpath(login_user.__name__, xpath_name)
                )
            except WebDriverException:
                candidates = []

            login_elem = next(
                (element for element in candidates if element.is_displayed()), None
            )
            if login_elem is not None:
                break

        if login_elem is None:
            logger.warning(
                "Login A/B test failed! Could not find the login form or a "
                "'Log in' button."
            )
            return False

    if login_elem is not None:
        click_element(browser, login_elem)

        # update server calls
        update_activity(browser, state=None)

        # The login page can load another cookie consent modal.
        accept_igcookie_dialogue(browser, logger)

    # Enter username and password and logs the user in
    # Sometimes the element name isn't 'Username' and 'Password'
    # (valid for placeholder too)

    # wait until it navigates to the login page
    # 10/2020 -> "WebDriver:GetTitle" - {"value":"Instagram"}
    login_page_title = "Instagram"
    explicit_wait(browser, "TC", login_page_title, logger)

    # wait until the 'username' input element is located and visible
    input_username_XP = read_xpath(login_user.__name__, "input_username_XP")
    explicit_wait(browser, "VOEL", [input_username_XP, "XPath"], logger)

    input_password_XP = read_xpath(login_user.__name__, "input_password")

    if not isinstance(password, str):
        password = str(password)

    # user
    username_filled = fill_login_field(browser, input_username_XP, username, logger)

    # update server calls for both 'click' and 'send_keys' actions
    for _ in range(2):
        update_activity(browser, state=None)

    sleep(1)

    # password
    password_filled = fill_login_field(browser, input_password_XP, password, logger)

    sleep(1)

    # React can still replace the fields shortly after the first fill, so
    # confirm both values survived before pressing "Log in".
    if (
        not username_filled
        or not password_filled
        or _login_field_value(browser, input_username_XP) != username
        or _login_field_value(browser, input_password_XP) != password
    ):
        username_filled = fill_login_field(browser, input_username_XP, username, logger)
        password_filled = fill_login_field(browser, input_password_XP, password, logger)

    if not username_filled or not password_filled:
        logger.warning("- Could not fill the login form")
        return False

    input_password = browser.find_element(By.XPATH, input_password_XP)

    # Submit the form. Modern Instagram renders the visible "Log in" control
    # as a <div role="button">; its <input type="submit"> is hidden, so a
    # plain ENTER key press is not always enough to trigger the login.
    submit_elem = None

    try:
        for candidate in browser.find_elements(
            By.XPATH, read_xpath(login_user.__name__, "login_submit")
        ):
            if candidate.is_displayed() and candidate.is_enabled():
                submit_elem = candidate
                break
    except WebDriverException:
        submit_elem = None

    if submit_elem is not None:
        # A JS click is used because the button is sometimes covered by a
        # full-page container that blocks Selenium's native click.
        browser.execute_script("arguments[0].click()", submit_elem)

        # update server call
        update_activity(browser, state=None)
    else:
        (
            ActionChains(browser)
            .move_to_element(input_password)
            .click()
            .send_keys(Keys.ENTER)
            .perform()
        )

        # update server calls for both 'click' and 'send_keys' actions
        for _ in range(2):
            update_activity(browser, state=None)

    # Wait until Instagram actually answers the login request before
    # deciding whether it succeeded.
    wait_for_login_outcome(browser, logger)

    # A visible error is a definitive failure and should be reported before
    # waiting for popups that only appear after a successful login.
    login_error = _find_login_error(browser)
    if login_error is not None:
        logger.warning(login_error.text)
        update_activity(
            browser,
            action=None,
            state=login_error.text,
            logfolder=logfolder,
            logger=logger,
        )
        return False

    # Check if account is protected with Two Factor Authentication
    two_factor_authentication(browser, logger, security_codes)

    # Dismiss following features if availables
    dismiss_get_app_offer(browser, logger)
    dismiss_notification_offer(browser, logger)
    dismiss_save_information(browser, logger)

    # IG: "Accept cookies from Instagram on this browser?"
    # They said that they're using cookies to help to personalize the content,
    # server relevant ads and provide safer experience.
    accept_igcookie_dialogue(browser, logger)

    # check for login error messages and display it in the logs
    if "instagram.com/challenge" in browser.current_url:
        # check if account is disabled by Instagram,
        # or there is an active challenge to solve
        try:
            account_disabled = browser.find_element(
                By.XPATH, read_xpath(login_user.__name__, "account_disabled")
            )
            logger.warning(account_disabled.text)
            update_activity(
                browser,
                action=None,
                state=account_disabled.text,
                logfolder=logfolder,
                logger=logger,
            )
            return False
        except NoSuchElementException:
            pass

        # in case the user doesnt have a phone number linked to the Instagram account
        try:
            browser.find_element(
                By.XPATH, read_xpath(login_user.__name__, "add_phone_number")
            )
            challenge_warn_msg = (
                "Instagram initiated a challenge before allow your account to login. "
                "At the moment there isn't a phone number linked to your Instagram "
                "account. Please, add a phone number to your account, and try again."
            )
            logger.warning(challenge_warn_msg)
            update_activity(
                browser,
                action=None,
                state=challenge_warn_msg,
                logfolder=logfolder,
                logger=logger,
            )
            return False
        except NoSuchElementException:
            pass

        # try to initiate security code challenge
        try:
            browser.find_element(
                By.XPATH, read_xpath(login_user.__name__, "suspicious_login_attempt")
            )
            update_activity(
                browser,
                action=None,
                state="Trying to solve suspicious attempt login",
                logfolder=logfolder,
                logger=logger,
            )
            bypass_suspicious_login(browser, logger, logfolder, security_code_to_phone)
        except NoSuchElementException:
            pass

    # check for wrong username or password message, and show it to the user
    error_alert = _find_login_error(browser)
    if error_alert is not None:
        logger.warning(error_alert.text)
        update_activity(
            browser,
            action=None,
            state=error_alert.text,
            logfolder=logfolder,
            logger=logger,
        )
        return False

    if "instagram.com/accounts/onetap" in browser.current_url:
        browser.get(ig_homepage)

    # wait until page fully load
    explicit_wait(browser, "PFL", [], logger, 5)

    # Check if user is logged-in (If there's two 'nav' elements)
    try:
        nav = browser.find_element(By.XPATH, read_xpath(login_user.__name__, "nav"))
    except NoSuchElementException:
        nav = None

    if nav is not None:
        # create cookie for username and save it
        cookies_list = browser.get_cookies()

        for cookie in cookies_list:
            if "sameSite" in cookie and cookie["sameSite"] == "None":
                cookie["sameSite"] = "Strict"

        try:
            # Open the cookie file to store the data
            with open(cookie_file, "wb") as cookie_f_handler:
                pickle.dump(cookies_list, cookie_f_handler)

        except pickle.PicklingError:
            # Next time, cookie will be created for the session so we are safe
            logger.warning("- Browser cookie list could not be saved to your local...")

        return True

    logger.warning(
        "- Login could not be confirmed (current URL: {})".format(
            browser.current_url
        )
    )
    return False


def dismiss_get_app_offer(browser, logger):
    """Dismiss 'Get the Instagram App' page after a fresh login"""
    offer_elem = read_xpath(dismiss_get_app_offer.__name__, "offer_elem")
    dismiss_elem = read_xpath(dismiss_get_app_offer.__name__, "dismiss_elem")

    # wait a bit and see if the 'Get App' offer rises up
    offer_loaded = explicit_wait(
        browser, "VOEL", [offer_elem, "XPath"], logger, 5, False
    )

    if offer_loaded:
        dismiss_elem = browser.find_element(By.XPATH, dismiss_elem)
        click_element(browser, dismiss_elem)


def dismiss_notification_offer(browser, logger):
    """Dismiss 'Turn on Notifications' offer on session start"""
    offer_elem_loc = read_xpath(dismiss_notification_offer.__name__, "offer_elem_loc")
    dismiss_elem_loc = read_xpath(
        dismiss_notification_offer.__name__, "dismiss_elem_loc"
    )

    # wait a bit and see if the 'Turn on Notifications' offer rises up
    offer_loaded = explicit_wait(
        browser, "VOEL", [offer_elem_loc, "XPath"], logger, 4, False
    )

    if offer_loaded:
        dismiss_elem = browser.find_element(By.XPATH, dismiss_elem_loc)
        click_element(browser, dismiss_elem)


def dismiss_save_information(browser, logger):
    """Dismiss 'Save Your Login Info?' offer on session start"""
    # This question occurs when pkl doesn't exist
    offer_elem_loc = read_xpath(dismiss_save_information.__name__, "offer_elem_loc")
    dismiss_elem_loc = read_xpath(dismiss_save_information.__name__, "dismiss_elem_loc")

    offer_loaded = explicit_wait(
        browser, "VOEL", [offer_elem_loc, "XPath"], logger, 4, False
    )

    if offer_loaded:
        # When prompted chose "Not Now", we don't know if saving information
        # contributes or stimulate IG to target the acct, it would be better to
        # just pretend that we are using IG in different browsers.
        logger.info("- Do not save Login Info by now...")
        dismiss_elem = browser.find_element(By.XPATH, dismiss_elem_loc)
        click_element(browser, dismiss_elem)


def dismiss_this_was_me(browser):
    try:
        # click on "This was me" button if challenge page was called
        this_was_me_button = browser.find_element(
            By.XPATH, read_xpath(dismiss_this_was_me.__name__, "this_was_me_button")
        )
        (ActionChains(browser).move_to_element(this_was_me_button).click().perform())
        # update server calls
        update_activity(browser, state=None)
    except NoSuchElementException:
        # no verification needed
        pass


def two_factor_authentication(browser, logger, security_codes):
    """
    Check if account is protected with Two Factor Authentication codes

    Args:
        :browser: Web driver
        :logger: Library to log actions
        :security_codes: List of Two Factor Authentication codes, also named as Recovery Codes.

    Returns: None
    """

    # Wait until page is loaded after user and password were introduced
    sleep(random.randint(3, 5))

    if "two_factor" in browser.current_url:

        logger.info("- Two Factor Authentication is enabled...")

        # Chose one code from the security_codes list
        # 0000 is used if no codes were provided in constructor.
        code = random.choice(security_codes)

        try:
            # Check Security code is numeric
            int(code)

            verification_code = read_xpath(login_user.__name__, "verification_code")
            explicit_wait(browser, "VOEL", [verification_code, "XPath"], logger)

            security_code = browser.find_element(By.XPATH, verification_code)

            #  Confirm blue button
            confirm = browser.find_element(
                By.XPATH, read_xpath(login_user.__name__, "confirm")
            )

            (
                ActionChains(browser)
                .move_to_element(security_code)
                .click()
                .send_keys(code)
                .perform()
            )

            sleep(random.randint(1, 3))

            (
                ActionChains(browser)
                .move_to_element(confirm)
                .click()
                .send_keys(Keys.ENTER)
                .perform()
            )

            # update server calls for both 'click' and 'send_keys' actions
            for _ in range(2):
                update_activity(browser, state=None)

            sleep(random.randint(1, 3))

        except NoSuchElementException as e:
            # Unable to login to Instagram!
            logger.warning(
                "- Secuirty code could not be written!\n\t{}".format(
                    str(e).encode("utf-8")
                )
            )
        except ValueError:
            # Unable to login to Instagram!
            logger.warning("- Secuirty code provided is not a number")
    else:
        # Two Factor Authentication is not enabled or the security code has
        # already been entered in previous session.
        # Return None and login to Instagram!
        return


def accept_igcookie_dialogue(browser, logger):
    """Presses 'Accept' button on IG cookie dialogue"""

    offer_elem_loc = read_xpath(accept_igcookie_dialogue.__name__, "accept_button")

    offer_loaded = explicit_wait(
        browser, "VOEL", [offer_elem_loc, "XPath"], logger, 4, False
    )

    if offer_loaded:
        logger.info("- Accepted IG cookies by default...")
        accept_elem = browser.find_element(By.XPATH, offer_elem_loc)
        click_element(browser, accept_elem)
