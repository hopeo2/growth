""" Quickstart script for InstaPy usage """

# imports
import os
import sys
from getpass import getpass

from instapy import InstaPy
from instapy import smart_run
from instapy import set_workspace


def cli_flag_present(*names):
    """Return True when one of the given CLI flags is present in argv."""
    for arg in sys.argv[1:]:
        if any(arg == name or arg.startswith(name + "=") for name in names):
            return True
    return False


def get_credentials():
    """Get credentials from the environment, CLI args, or prompt for them."""
    username = os.environ.get("INSTA_USER")
    password = os.environ.get("INSTA_PW")

    # Only prompt when attached to a terminal; otherwise just let the checks
    # below print a helpful message.
    if not sys.stdin.isatty():
        return username, password

    if not username and not cli_flag_present("--username"):
        try:
            username = input("Instagram username: ").strip() or None
        except EOFError:
            pass

    if not password and not cli_flag_present("--password"):
        try:
            password = getpass("Instagram password: ") or None
        except EOFError:
            pass

    return username, password


# set workspace folder at desired location (default is at your home folder)
set_workspace(path=None)

username, password = get_credentials()

if not username and not cli_flag_present("--username"):
    sys.exit(
        "No Instagram username given. Pass it to InstaPy(username=...), set "
        "INSTA_USER, or run with `--username`."
    )
if not password and not cli_flag_present("--password"):
    sys.exit(
        "No Instagram password given. Pass it to InstaPy(password=...), set "
        "INSTA_PW, or run with `--password`."
    )

# get an InstaPy session!
session = InstaPy(username=username, password=password)

with smart_run(session):
    # general settings
    session.set_dont_include(["friend1", "friend2", "friend3"])

    # activity
    session.like_by_tags(["natgeo"], amount=10)
