# import built-in & third-party modules
import glob
import json
import os
import random
import re
from datetime import datetime

import requests

# import exceptions
from selenium.common.exceptions import WebDriverException

# import InstaPy modules
from .follow_util import get_following_status
from .settings import Settings
from .time_util import sleep
from .util import (
    get_relationship_counts,
    interruption_handler,
    is_private_profile,
    update_activity,
    web_address_navigator,
)

# Instagram's web API expects the public web app id and the browser's cookies.
# The old ``window._sharedData`` / ``view-source:`` GraphQL scraping is no
# longer served by Instagram, so relationship data is read through this API.
_IG_WEB_APP_ID = "936619743392459"
_IG_WEB_API = "https://www.instagram.com/api/v1"


def _build_api_session(browser):
    """Return a ``requests`` session using the logged-in browser's cookies."""
    session = requests.Session()
    csrftoken = ""

    try:
        cookies = browser.get_cookies()
    except WebDriverException:
        cookies = []

    for cookie in cookies:
        name = cookie.get("name")
        if not name:
            continue

        session.cookies.set(
            name,
            cookie.get("value", ""),
            domain=cookie.get("domain"),
            path=cookie.get("path") or "/",
        )
        if name == "csrftoken":
            csrftoken = cookie.get("value", "")

    return session, csrftoken


def _api_headers(csrftoken):
    headers = {
        "User-Agent": Settings.user_agent,
        "Accept": "*/*",
        "X-IG-App-ID": _IG_WEB_APP_ID,
        # The web app always sends these; without them Instagram can answer
        # with an HTML login/challenge page instead of JSON.
        "X-IG-WWW-Claim": "0",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.instagram.com/",
        "Origin": "https://www.instagram.com",
    }
    if csrftoken:
        headers["X-CSRFToken"] = csrftoken
    return headers


def _get_web_profile_info(session, headers, username, logger):
    """Fetch a user's profile information from Instagram's web API."""
    try:
        response = session.get(
            "{}/users/web_profile_info/".format(_IG_WEB_API),
            params={"username": username},
            headers=headers,
            timeout=30,
        )
    except requests.RequestException as exc:
        logger.info(
            "Unable to get profile information of '{}':\n\t{}".format(username, exc)
        )
        return None

    if response.status_code != 200:
        logger.info(
            "Instagram profile API returned HTTP {} for '{}'".format(
                response.status_code, username
            )
        )
        return None

    try:
        return (response.json().get("data") or {}).get("user")
    except (ValueError, AttributeError):
        return None


def _user_id_from_cookie(browser):
    """Read the logged-in user id directly from the browser cookies."""
    try:
        for cookie in browser.get_cookies():
            if cookie.get("name") == "ds_user_id":
                return cookie.get("value")
    except WebDriverException:
        pass
    return None


def _user_id_from_page(browser, username):
    """Try to find a user id in the loaded profile page's embedded JSON."""
    try:
        source = browser.page_source or ""
    except WebDriverException:
        return None

    escaped = re.escape(username)
    patterns = (
        r'"username":"{}"[^{{}}]{{0,300}}?"id":"(\d+)"'.format(escaped),
        r'"id":"(\d+)"[^{{}}]{{0,300}}?"username":"{}"'.format(escaped),
        r'"username":"{}"[^{{}}]{{0,300}}?"pk":"(\d+)"'.format(escaped),
        r'"pk":"(\d+)"[^{{}}]{{0,300}}?"username":"{}"'.format(escaped),
    )
    for pattern in patterns:
        match = re.search(pattern, source)
        if match:
            return match.group(1)

    return None


def _resolve_user_id(browser, username, self_username, user_info, logger):
    """Resolve a username to its numeric Instagram user id."""
    if user_info and user_info.get("id"):
        return str(user_info["id"])

    if username == self_username:
        user_id = _user_id_from_cookie(browser)
        if user_id:
            return str(user_id)

    user_id = _user_id_from_page(browser, username)
    if user_id:
        return user_id

    # Last resort: legacy page globals, guarded so a missing object is not
    # fatal (modern Instagram no longer exposes them).
    try:
        user_id = browser.execute_script(
            "return (window._sharedData && window._sharedData.entry_data && "
            "window._sharedData.entry_data.ProfilePage) ? "
            "window._sharedData.entry_data.ProfilePage[0].graphql.user.id : null;"
        )
    except WebDriverException:
        user_id = None

    if user_id:
        return str(user_id)

    logger.info("Unable to determine the user ID of '{}'".format(username))
    return None


def _api_failure_detail(response):
    """Return a short, safe description of an unusable API response."""
    status = getattr(response, "status_code", "?")
    headers = getattr(response, "headers", None) or {}
    try:
        content_type = headers.get("Content-Type", "unknown")
    except AttributeError:
        content_type = "unknown"

    text = getattr(response, "text", None)
    snippet = ""
    if isinstance(text, str):
        snippet = text.strip().replace("\n", " ")[:160]

    return "HTTP {}  |  content-type: {}  |  body: {!r}".format(
        status, content_type, snippet
    )


def _get_relationship_page_in_browser(
    browser, user_id, relationship, max_id, logger
):
    """Fetch one page of relationship data from inside the logged-in page.

    Instagram sometimes answers the private API with an HTML login or
    challenge page even though the browser itself is still signed in. Running
    the very same request in the page makes the browser attach its own
    cookies, user agent and headers, which keeps the request valid where the
    copied ``requests`` session is not.
    """
    endpoint = "/api/v1/friendships/{}/{}/?count=50".format(user_id, relationship)
    if max_id:
        endpoint += "&max_id={}".format(max_id)

    # Keep the script bounded so a hanging fetch cannot stall the session.
    try:
        browser.set_script_timeout(30)
    except Exception:
        pass

    script = (
        "const done = arguments[arguments.length - 1];"
        "const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);"
        "const headers = {'x-ig-app-id': arguments[1],"
        " 'x-ig-www-claim': '0',"
        " 'x-requested-with': 'XMLHttpRequest'};"
        "if (match) { headers['x-csrftoken'] = decodeURIComponent(match[1]); }"
        "fetch(arguments[0], {credentials: 'include', headers: headers})"
        ".then(function (response) { return response.text(); })"
        ".then(function (body) { done(body); })"
        ".catch(function (error) { done({error: String(error)}); });"
    )

    try:
        body = browser.execute_async_script(script, endpoint, _IG_WEB_APP_ID)
    except Exception as exc:  # a missing/unusable browser must not be fatal
        logger.info(
            "In-browser `{}` request failed:\n\t{}".format(
                relationship.capitalize(), exc
            )
        )
        return None

    if not isinstance(body, str) or not body:
        return None

    try:
        return json.loads(body)
    except ValueError:
        return None


def _get_relationship_page(
    browser, session, headers, user_id, relationship, max_id, logger
):
    """Return one page of relationship data as a dict, or ``None``.

    The ``requests`` session is tried first because it is fast. If Instagram
    answers with something that is not JSON (a login or challenge page, for
    instance) the request is repeated from inside the browser, which is served
    by the account's live session instead of the copied cookies.
    """
    endpoint = "{}/friendships/{}/{}/".format(_IG_WEB_API, user_id, relationship)
    params = {"count": 50}
    if max_id:
        params["max_id"] = max_id

    try:
        response = session.get(endpoint, params=params, headers=headers, timeout=30)
        update_activity(browser, state=None)

        if response.status_code == 200:
            try:
                return response.json()
            except ValueError:
                logger.info(
                    "Instagram `{}` API returned invalid JSON ({})  "
                    "~retrying in the browser".format(
                        relationship.capitalize(), _api_failure_detail(response)
                    )
                )
        else:
            logger.info(
                "Instagram `{}` API returned HTTP {} for user ID {}  "
                "~retrying in the browser".format(
                    relationship.capitalize(), response.status_code, user_id
                )
            )
    except requests.RequestException as exc:
        logger.info(
            "Unable to get `{}` data:\n\t{}".format(relationship.capitalize(), exc)
        )

    return _get_relationship_page_in_browser(
        browser, user_id, relationship, max_id, logger
    )


def _get_relationship_usernames(
    browser,
    session,
    headers,
    user_id,
    relationship,
    amount,
    logger,
    verified_only=False,
):
    """Read followers/following through Instagram's web API.

    ``relationship`` is either ``"followers"`` or ``"following"``. The API
    paginates with ``next_max_id``; a ``count`` of 50 is the web app's page
    size. ``amount`` can be ``"full"`` or a positive integer.
    """
    usernames = []
    max_id = None
    seen_cursors = set()
    complete = True

    while True:
        data = _get_relationship_page(
            browser, session, headers, user_id, relationship, max_id, logger
        )

        if data is None:
            complete = False
            break

        if data.get("status") == "fail":
            logger.info(
                "Instagram `{}` API returned an error: {}".format(
                    relationship.capitalize(), data.get("message")
                )
            )
            complete = False
            break

        for user in data.get("users") or []:
            if verified_only and not user.get("is_verified"):
                continue
            name = user.get("username")
            if name:
                usernames.append(name)

        if amount != "full" and len(set(usernames)) >= amount:
            break

        next_max_id = data.get("next_max_id")
        if not next_max_id or next_max_id in seen_cursors:
            break

        seen_cursors.add(next_max_id)
        max_id = next_max_id
        sleep(random.randint(2, 4))

    # Remove duplicates while preserving the API's order.
    usernames = list(dict.fromkeys(usernames))

    if not complete and (amount == "full" or len(usernames) < amount):
        # A partial list must never be used for follower/non-follower
        # comparisons; doing so would mark real followers as non-followers.
        logger.info(
            "`{}` data is incomplete  ~discarding partial results".format(
                relationship.capitalize()
            )
        )
        return []

    if amount != "full":
        usernames = usernames[:amount]

    return usernames


def get_followers(
    browser,
    self_username,
    username,
    grab,
    relationship_data,
    live_match,
    store_locally,
    logger,
    logfolder,
    verified_only=False,
):
    """Get entire list of followers using Instagram's web API."""

    all_followers = []

    if username not in relationship_data:
        relationship_data.update({username: {"all_following": [], "all_followers": []}})

    grab_info = (
        'at "full" range' if grab == "full" else "at the range of {}".format(grab)
    )
    tense = (
        "live"
        if (live_match is True or not relationship_data[username]["all_followers"])
        else "fresh"
    )

    logger.info(
        "Retrieving {} `Followers` data of {} {}".format(tense, username, grab_info)
    )

    user_link = "https://www.instagram.com/{}/".format(username)
    web_address_navigator(browser, user_link)

    # Get followers count
    followers_count, _ = get_relationship_counts(browser, username, logger)

    if grab != "full" and followers_count is not None and grab > followers_count:
        logger.info(
            "You have requested higher amount than existing followers count "
            " ~gonna grab all available"
        )
        grab = followers_count

    # Check if user's account is private and we don't follow
    following_status, _ = get_following_status(
        browser, "profile", self_username, username, None, logger, logfolder
    )

    session, csrftoken = _build_api_session(browser)
    headers = _api_headers(csrftoken)

    user_info = None
    is_private = None
    if username != self_username:
        user_info = _get_web_profile_info(session, headers, username, logger)
        if user_info:
            is_private = user_info.get("is_private")
            if followers_count is None:
                followers_count = (
                    user_info.get("edge_followed_by") or {}
                ).get("count")
        else:
            is_private = is_private_profile(
                browser, logger, following_status == "Following"
            )

    if not username == self_username and (
        (is_private is True and following_status not in ["Following", True])
        or (following_status == "Blocked")
    ):
        logger.info(
            "This user is private and we are not following. '{}':'{}'".format(
                is_private, following_status
            )
        )
        return all_followers

    user_id = _resolve_user_id(browser, username, self_username, user_info, logger)
    if not user_id:
        logger.info(
            "Unable to get `Followers` data of '{}'  ~empty list".format(username)
        )
        return all_followers

    all_followers = _get_relationship_usernames(
        browser,
        session,
        headers,
        user_id,
        "followers",
        grab,
        logger,
        verified_only=verified_only,
    )

    if len(all_followers) > 0:
        if (
            store_locally is True
            and relationship_data[username]["all_followers"] != all_followers
        ):
            store_followers_data(username, grab, all_followers, logger, logfolder)
        elif store_locally is True:
            logger.info(
                "The `Followers` data is identical with the data in previous "
                "query  ~not storing the file again"
            )

        if grab == "full":
            relationship_data[username].update({"all_followers": all_followers})

    logger.info("Grabbed {} usernames from `Followers`".format(len(all_followers)))

    return all_followers


def get_following(
    browser,
    self_username,
    username,
    grab,
    relationship_data,
    live_match,
    store_locally,
    logger,
    logfolder,
):
    """Get entire list of following using Instagram's web API."""

    all_following = []

    if username not in relationship_data:
        relationship_data.update({username: {"all_following": [], "all_followers": []}})

    grab_info = (
        'at "full" range' if grab == "full" else "at the range of {}".format(grab)
    )
    tense = (
        "live"
        if (live_match is True or not relationship_data[username]["all_following"])
        else "fresh"
    )

    logger.info(
        "Retrieving {} `Following` data of {} {}".format(tense, username, grab_info)
    )

    user_link = "https://www.instagram.com/{}/".format(username)
    web_address_navigator(browser, user_link)

    # Get following count
    _, following_count = get_relationship_counts(browser, username, logger)

    if grab != "full" and following_count is not None and grab > following_count:
        logger.info(
            "You have requested higher amount than existing following count "
            " ~gonna grab all available"
        )
        grab = following_count

    # Check if user's account is private and we don't follow
    following_status, _ = get_following_status(
        browser, "profile", self_username, username, None, logger, logfolder
    )

    session, csrftoken = _build_api_session(browser)
    headers = _api_headers(csrftoken)

    user_info = None
    is_private = None
    if username != self_username:
        user_info = _get_web_profile_info(session, headers, username, logger)
        if user_info:
            is_private = user_info.get("is_private")
            if following_count is None:
                following_count = (user_info.get("edge_follow") or {}).get("count")
        else:
            is_private = is_private_profile(
                browser, logger, following_status == "Following"
            )

    if not username == self_username and (
        (is_private is True and following_status not in ["Following", True])
        or (following_status == "Blocked")
    ):
        logger.info(
            "This user is private and we are not following. '{}':'{}'".format(
                is_private, following_status
            )
        )
        return all_following

    user_id = _resolve_user_id(browser, username, self_username, user_info, logger)
    if not user_id:
        logger.info(
            "Unable to get `Following` data of '{}'  ~empty list".format(username)
        )
        return all_following

    all_following = _get_relationship_usernames(
        browser,
        session,
        headers,
        user_id,
        "following",
        grab,
        logger,
    )

    if len(all_following) > 0:
        if (
            store_locally is True
            and relationship_data[username]["all_following"] != all_following
        ):
            store_following_data(username, grab, all_following, logger, logfolder)
        elif store_locally is True:
            logger.info(
                "The `Following` data is identical with the data in previous "
                "query  ~not storing the file again"
            )

        if grab == "full":
            relationship_data[username].update({"all_following": all_following})

    logger.info("Grabbed {} usernames from `Following`".format(len(all_following)))

    return all_following


def get_unfollowers(
    browser,
    self_username,
    username,
    compare_by,
    compare_track,
    relationship_data,
    live_match,
    store_locally,
    print_out,
    logger,
    logfolder,
):
    if compare_by not in ["latest", "day", "month", "year", "earliest"]:
        logger.info(
            "Please choose a valid compare point to pick Unfollowers  "
            "~leaving out of an invalid value"
        )
        return [], []

    elif compare_track not in ["first", "median", "last"]:
        logger.info(
            "Please choose a valid compare track to pick Unfollowers  "
            "~leaving out of an invalid value"
        )
        return [], []

    elif username is None or not isinstance(username, str):
        logger.info(
            "Please enter a username to pick Unfollowers  ~leaving out of an "
            "invalid value"
        )
        return [], []

    prior_followers, selected_filename = load_followers_data(
        username, compare_by, compare_track, logger, logfolder
    )

    if not prior_followers and selected_filename is None:
        logger.info(
            "Generate `Followers` data to find Unfollowers in future!  "
            "~couldn't pick Unfollowers"
        )
        return [], []

    current_followers = get_followers(
        browser,
        self_username,
        username,
        "full",
        relationship_data,
        live_match,
        store_locally,
        logger,
        logfolder,
    )

    # if current_followers is False we have targeted a private account that we don't follow
    if not current_followers:
        return False, False

    all_unfollowers = [
        follower for follower in prior_followers if follower not in current_followers
    ]

    if len(all_unfollowers) > 0:
        current_following = get_following(
            browser,
            self_username,
            username,
            "full",
            relationship_data,
            live_match,
            store_locally,
            logger,
            logfolder,
        )

        active_unfollowers = [
            unfollower
            for unfollower in current_following
            if unfollower in all_unfollowers
        ]

        logger.info(
            "Unfollowers found from {}!  total: {}  |  active: {}  "
            ":|\n".format(
                selected_filename, len(all_unfollowers), len(active_unfollowers)
            )
        )
        if store_locally is True:
            # store all Unfollowers in a local file
            store_all_unfollowers(username, all_unfollowers, logger, logfolder)
            # store active Unfollowers in a local file
            store_active_unfollowers(username, active_unfollowers, logger, logfolder)

        if print_out is True:
            logger.info(
                "Unfollowers of {}:\n\n\tAll Unfollowers: {}\n\n\tActive "
                "Unfollowers: {}\n".format(
                    username, all_unfollowers, active_unfollowers
                )
            )
    else:
        logger.info(
            "Yay! You have no any Unfollowers from {}!  ^v^".format(selected_filename)
        )
        return [], []

    return all_unfollowers, active_unfollowers


def get_nonfollowers(
    browser,
    self_username,
    username,
    relationship_data,
    live_match,
    store_locally,
    logger,
    logfolder,
):
    """Finds Nonfollowers of a given user"""

    if username is None or not isinstance(username, str):
        logger.info(
            "Please enter a username to pick Nonfollowers  ~leaving out of "
            "an invalid value"
        )
        return []

    # get `Followers` data
    all_followers = get_followers(
        browser,
        self_username,
        username,
        "full",
        relationship_data,
        live_match,
        store_locally,
        logger,
        logfolder,
    )

    # No followers data means the account is private/unavailable, or the API
    # request failed. Return an empty list so callers can safely check length.
    if not all_followers:
        return []

    # get `Following` data
    all_following = get_following(
        browser,
        self_username,
        username,
        "full",
        relationship_data,
        live_match,
        store_locally,
        logger,
        logfolder,
    )

    # using this approach we can preserve the order of elements to be used
    # with `FIFO`, `LIFO` or `RANDOM` styles
    nonfollowers = [user for user in all_following if user not in all_followers]

    # uniqify elements
    nonfollowers = sorted(set(nonfollowers), key=nonfollowers.index)

    logger.info(
        "There are {0} Nonfollowers of {1}  ~the users {1} is following WHO "
        "do not follow back\n".format(len(nonfollowers), username)
    )

    # store Nonfollowers' data in a local file
    store_nonfollowers(
        username,
        len(all_followers),
        len(all_following),
        nonfollowers,
        logger,
        logfolder,
    )

    return nonfollowers


def get_fans(
    browser,
    self_username,
    username,
    relationship_data,
    live_match,
    store_locally,
    logger,
    logfolder,
):
    """Find Fans of a given user"""

    if username is None or not isinstance(username, str):
        logger.info(
            "Please enter a username to pick Fans  ~leaving out of an invalid value"
        )
        return []

    # get `Followers` data
    all_followers = get_followers(
        browser,
        self_username,
        username,
        "full",
        relationship_data,
        live_match,
        store_locally,
        logger,
        logfolder,
    )

    # No followers data means the account is private/unavailable, or the API
    # request failed. Return an empty list so callers can safely check length.
    if not all_followers:
        return []

    # get `Following` data
    all_following = get_following(
        browser,
        self_username,
        username,
        "full",
        relationship_data,
        live_match,
        store_locally,
        logger,
        logfolder,
    )

    # using this approach we can preserve the order of elements to be used
    # with `FIFO`, `LIFO` or `RANDOM` styles
    fans = [user for user in all_followers if user not in all_following]

    # uniqify elements
    fans = sorted(set(fans), key=fans.index)

    logger.info(
        "There are {0} Fans of {1}  ~the users following {1} WHOM {1} does "
        "not follow back\n".format(len(fans), username)
    )

    # store Nonfollowers data in a local file
    store_fans(
        username, len(all_followers), len(all_following), fans, logger, logfolder
    )

    return fans


def get_mutual_following(
    browser,
    self_username,
    username,
    relationship_data,
    live_match,
    store_locally,
    logger,
    logfolder,
):
    """Find Mutual Following of a given user"""

    if username is None or type(username) != str:
        logger.info(
            "Please enter a username to pick Mutual Following  ~leaving out "
            "of an invalid value"
        )
        return []

    # get `Followers` data
    all_followers = get_followers(
        browser,
        self_username,
        username,
        "full",
        relationship_data,
        live_match,
        store_locally,
        logger,
        logfolder,
    )

    # No followers data means the account is private/unavailable, or the API
    # request failed. Return an empty list so callers can safely check length.
    if not all_followers:
        return []

    # get `Following` data
    all_following = get_following(
        browser,
        self_username,
        username,
        "full",
        relationship_data,
        live_match,
        store_locally,
        logger,
        logfolder,
    )

    # using this approach we can preserve the order of elements to be used
    # with `FIFO`, `LIFO` or `RANDOM` styles
    mutual_following = [user for user in all_following if user in all_followers]

    # uniqify elements
    mutual_following = sorted(set(mutual_following), key=mutual_following.index)

    logger.info(
        "There are {0} Mutual Following of {1}  ~the users {1} is following "
        "WHO also follow back\n".format(len(mutual_following), username)
    )

    # store Mutual Following data in a local file
    store_mutual_following(
        username,
        len(all_followers),
        len(all_following),
        mutual_following,
        logger,
        logfolder,
    )

    return mutual_following


def store_followers_data(username, grab, grabbed_followers, logger, logfolder):
    """Store grabbed `Followers` data in a local storage at generated date"""
    query_date = datetime.today().strftime("%d-%m-%Y")
    grabbed_followers_size = len(grabbed_followers)
    file_directory = "{}/relationship_data/{}/followers/".format(logfolder, username)
    file_name = "{}{}~{}~{}".format(
        file_directory, query_date, grab, grabbed_followers_size
    )
    file_index = 0
    final_file = "{}.json".format(file_name)

    try:
        if not os.path.exists(file_directory):
            os.makedirs(file_directory)
        # this loop provides unique data files
        while os.path.isfile(final_file):
            file_index += 1
            final_file = "{}({}).json".format(file_name, file_index)

        with open(final_file, "w") as followers_data:
            with interruption_handler():
                json.dump(grabbed_followers, followers_data)
        logger.info("Stored `Followers` data at {} local file".format(final_file))

    except Exception as exc:
        logger.info(
            "Failed to store `Followers` data in a local file :Z\n{}".format(
                str(exc).encode("utf-8")
            )
        )


def store_following_data(username, grab, grabbed_following, logger, logfolder):
    """Store grabbed `Following` data in a local storage at generated date"""
    query_date = datetime.today().strftime("%d-%m-%Y")
    grabbed_following_size = len(grabbed_following)
    file_directory = "{}/relationship_data/{}/following/".format(logfolder, username)
    file_name = "{}{}~{}~{}".format(
        file_directory, query_date, grab, grabbed_following_size
    )
    file_index = 0
    final_file = "{}.json".format(file_name)

    try:
        if not os.path.exists(file_directory):
            os.makedirs(file_directory)
        # this loop provides unique data files
        while os.path.isfile(final_file):
            file_index += 1
            final_file = "{}({}).json".format(file_name, file_index)

        with open(final_file, "w") as following_data:
            with interruption_handler():
                json.dump(grabbed_following, following_data)
        logger.info("Stored `Following` data at {} local file".format(final_file))

    except Exception as exc:
        logger.info(
            "Failed to store `Following` data in a local file :Z\n{}".format(
                str(exc).encode("utf-8")
            )
        )


def store_all_unfollowers(username, all_unfollowers, logger, logfolder):
    """Store all Unfollowers data in a local storage at generated date"""
    generation_date = datetime.today().strftime("%d-%m-%Y")
    all_unfollowers_size = len(all_unfollowers)
    file_directory = "{}/relationship_data/{}/unfollowers/all_unfollowers/".format(
        logfolder, username
    )
    file_name = "{}{}~all~{}".format(
        file_directory, generation_date, all_unfollowers_size
    )
    file_index = 0
    final_file = "{}.json".format(file_name)

    try:
        if not os.path.exists(file_directory):
            os.makedirs(file_directory)
        # this loop provides unique data files
        while os.path.isfile(final_file):
            file_index += 1
            final_file = "{}({}).json".format(file_name, file_index)

        with open(final_file, "w") as unfollowers_data:
            with interruption_handler():
                json.dump(all_unfollowers, unfollowers_data)
        logger.info("Stored all Unfollowers data at {} local file\n".format(final_file))

    except Exception as exc:
        logger.info(
            "Failed to store all Unfollowers data in a local file :Z\n{}"
            "\n".format(str(exc).encode("utf-8"))
        )


def store_active_unfollowers(username, active_unfollowers, logger, logfolder):
    """Store active Unfollowers data in a local storage at generated date"""
    generation_date = datetime.today().strftime("%d-%m-%Y")
    active_unfollowers_size = len(active_unfollowers)
    file_directory = (
        "{}/relationship_data/{}"
        "/unfollowers/active_unfollowers/".format(logfolder, username)
    )
    file_name = "{}{}~active~{}".format(
        file_directory, generation_date, active_unfollowers_size
    )
    file_index = 0
    final_file = "{}.json".format(file_name)

    try:
        if not os.path.exists(file_directory):
            os.makedirs(file_directory)
        # this loop provides unique data files
        while os.path.isfile(final_file):
            file_index += 1
            final_file = "{}({}).json".format(file_name, file_index)

        with open(final_file, "w") as active_unfollowers_data:
            with interruption_handler():
                json.dump(active_unfollowers, active_unfollowers_data)
        logger.info(
            "Stored active Unfollowers data at {} local file\n".format(final_file)
        )

    except Exception as exc:
        logger.info(
            "Failed to store active Unfollowers data in a local file :Z\n{}"
            "\n".format(str(exc).encode("utf-8"))
        )


def store_nonfollowers(
    username, followers_size, following_size, nonfollowers, logger, logfolder
):
    """Store Nonfollowers data in a local storage at generated date"""
    generation_date = datetime.today().strftime("%d-%m-%Y")
    nonfollowers_size = len(nonfollowers)
    file_directory = "{}/relationship_data/{}/nonfollowers/".format(logfolder, username)
    file_name = "{}{}~[{}-{}]~{}".format(
        file_directory,
        generation_date,
        followers_size,
        following_size,
        nonfollowers_size,
    )
    file_index = 0
    final_file = "{}.json".format(file_name)

    try:
        if not os.path.exists(file_directory):
            os.makedirs(file_directory)
        # this loop provides unique data files
        while os.path.isfile(final_file):
            file_index += 1
            final_file = "{}({}).json".format(file_name, file_index)

        with open(final_file, "w") as nonfollowers_data:
            with interruption_handler():
                json.dump(nonfollowers, nonfollowers_data)
        logger.info("Stored Nonfollowers data at {} local file\n".format(final_file))

    except Exception as exc:
        logger.info(
            "Failed to store Nonfollowers data in a local file :Z\n{}"
            "\n".format(str(exc).encode("utf-8"))
        )


def store_fans(username, followers_size, following_size, fans, logger, logfolder):
    """Store Fans data in a local storage at generated date"""
    generation_date = datetime.today().strftime("%d-%m-%Y")
    fans_size = len(fans)

    file_directory = "{}/relationship_data/{}/fans/".format(logfolder, username)
    file_name = "{}{}~[{}-{}]~{}".format(
        file_directory, generation_date, followers_size, following_size, fans_size
    )

    file_index = 0
    final_file = "{}.json".format(file_name)

    try:
        if not os.path.exists(file_directory):
            os.makedirs(file_directory)
        # this loop provides unique data files
        while os.path.isfile(final_file):
            file_index += 1
            final_file = "{}({}).json".format(file_name, file_index)

        with open(final_file, "w") as fans_data:
            with interruption_handler():
                json.dump(fans, fans_data)
        logger.info("Stored Fans data at {} local file\n".format(final_file))

    except Exception as exc:
        logger.info(
            "Failed to store Fans data in a local file :Z\n{}\n".format(
                str(exc).encode("utf-8")
            )
        )


def store_mutual_following(
    username, followers_size, following_size, mutual_following, logger, logfolder
):
    """Store Mutual Following data in a local storage at generated date"""
    generation_date = datetime.today().strftime("%d-%m-%Y")
    mutual_following_size = len(mutual_following)

    file_directory = "{}/relationship_data/{}/mutual_following/".format(
        logfolder, username
    )
    file_name = "{}{}~[{}-{}]~{}".format(
        file_directory,
        generation_date,
        followers_size,
        following_size,
        mutual_following_size,
    )

    file_index = 0
    final_file = "{}.json".format(file_name)

    try:
        if not os.path.exists(file_directory):
            os.makedirs(file_directory)
        # this loop provides unique data files
        while os.path.isfile(final_file):
            file_index += 1
            final_file = "{}({}).json".format(file_name, file_index)

        with open(final_file, "w") as mutual_following_data:
            with interruption_handler():
                json.dump(mutual_following, mutual_following_data)
        logger.info(
            "Stored Mutual Following data at {} local file\n".format(final_file)
        )

    except Exception as exc:
        logger.info(
            "Failed to store Mutual Following data in a local file :Z\n{}"
            "\n".format(str(exc).encode("utf-8"))
        )


def load_followers_data(username, compare_by, compare_track, logger, logfolder):
    """Write grabbed `followers` data into local storage"""

    # Variables
    tracked_filenames = []
    structured_entries = {}
    selected_filename = None

    # get the list of all existing FULL `Followers` data files in
    # ~/logfolder/username/followers/ location
    files_location = "{}/relationship_data/{}/followers".format(logfolder, username)
    followers_data_files = [
        os.path.basename(file)
        for file in glob.glob("{}/*~full*.json".format(files_location))
    ]

    # check if there is any file to be compared
    if not followers_data_files:
        logger.info(
            "There are no any `Followers` data files in the {} location to "
            "compare".format(files_location)
        )
        return [], None

    # Filtrate and get the right track of file to compare
    for data_file in followers_data_files:
        tracked_filenames.append(data_file[:10])
    sorted_filenames = sorted(
        tracked_filenames, key=lambda x: datetime.strptime(x, "%d-%m-%Y")
    )

    this_day = datetime.today().strftime("%d")
    this_month = datetime.today().strftime("%m")
    this_year = datetime.today().strftime("%Y")

    for entry in sorted_filenames:
        entry_day, entry_month, entry_year = entry.split("-")

        structured_entries.setdefault("years", {}).setdefault(
            entry_year, {}
        ).setdefault("months", {}).setdefault(entry_month, {}).setdefault(
            "days", {}
        ).setdefault(
            entry_day, {}
        ).setdefault(
            "entries", []
        ).append(
            entry
        )

    if compare_by == "latest":
        selected_filename = sorted_filenames[-1]

    elif compare_by == "day":
        latest_day = sorted_filenames[-1]
        current_day = datetime.today().strftime("%d-%m-%Y")

        if latest_day == current_day:
            data_for_today = structured_entries["years"][this_year]["months"][
                this_month
            ]["days"][this_day]["entries"]

            if compare_track == "first" or len(data_for_today) <= 1:
                selected_filename = data_for_today[0]
            if compare_track == "median":
                median_index = int(len(data_for_today) / 2)
                selected_filename = data_for_today[median_index]
            if compare_track == "last":
                selected_filename = data_for_today[-1]

        else:
            selected_filename = sorted_filenames[-1]
            logger.info(
                "No any data exists for today!  ~choosing the last existing "
                "data from {}".format(selected_filename)
            )

    elif compare_by == "month":
        latest_month = sorted_filenames[-1][-7:]
        current_month = datetime.today().strftime("%m-%Y")

        if latest_month == current_month:
            data_for_month = []

            for day in structured_entries["years"][this_year]["months"][this_month][
                "days"
            ]:
                data_for_month.extend(
                    structured_entries["years"][this_year]["months"][this_month][
                        "days"
                    ][day]["entries"]
                )

            if compare_track == "first" or len(data_for_month) <= 1:
                selected_filename = data_for_month[0]
            if compare_track == "median":
                median_index = int(len(data_for_month) / 2)
                selected_filename = data_for_month[median_index]
            if compare_track == "last":
                selected_filename = data_for_month[-1]

        else:
            selected_filename = sorted_filenames[-1]
            logger.info(
                "No any data exists for this month!  ~choosing the last "
                "existing data from {}".format(selected_filename)
            )

    elif compare_by == "year":
        latest_year = sorted_filenames[-1][-4:]

        if latest_year == this_year:
            data_for_year = []

            for month in structured_entries["years"][this_year]["months"]:
                for day in structured_entries["years"][this_year]["months"][month][
                    "days"
                ]:
                    data_for_year.extend(
                        structured_entries["years"][this_year]["months"][month]["days"][
                            day
                        ]["entries"]
                    )

            if compare_track == "first" or len(data_for_year) <= 1:
                selected_filename = data_for_year[0]
            if compare_track == "median":
                median_index = int(len(data_for_year) / 2)
                selected_filename = data_for_year[median_index]
            if compare_track == "last":
                selected_filename = data_for_year[-1]

        else:
            selected_filename = sorted_filenames[-1]
            logger.info(
                "No any data exists for this year!  ~choosing the last existing data from {}".format(
                    selected_filename
                )
            )

    elif compare_by == "earliest":
        selected_filename = sorted_filenames[0]

    # load that file
    selected_file = (
        glob.glob("{}/{}~full*.json".format(files_location, selected_filename))
    )[0]
    with open(selected_file) as followers_data_file:
        followers_data = json.load(followers_data_file)

    logger.info(
        "Took prior `Followers` data file from {} with {} usernames "
        "to be compared with live data\n".format(selected_filename, len(followers_data))
    )

    # return that file to be compared
    return followers_data, selected_filename
