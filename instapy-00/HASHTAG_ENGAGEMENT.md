# Hashtag follow / like / comment automation

`hashtag_engagement.py` searches a curated mix of Persian mutual-support tags
and popular/trending hashtags and, for each post it finds:

1. likes the post,
2. posts one Persian comment from your list,
3. follows the author of the post (only once per author),
4. unfollows authors that have not followed back within 3 days and never
   follows them again.

After the hashtag loop it also engages with the accounts the bot already
follows:

5. watches their stories,
6. likes comments on their recent posts,
7. replies to a percentage of the comments it liked.

It uses the existing InstaPy package in this folder.

Comments are not chosen with a plain `random.choice` anymore: InstaPy cycles
through a shuffled "deck", so every comment is posted once before any comment
is repeated. The built-in list contains 72 varied Persian comments plus 12
replies.

> **No automation can guarantee that an account will never be blocked.**
> The script is deliberately slow and bounded, but you still use it at your
> own risk. Prefer a secondary account you can afford to lose.

## Safety restrictions enabled by default

| Protection | Default |
| --- | --- |
| Posts processed per hashtag | `1` |
| Candidate posts inspected per hashtag | `5` |
| Follow rate | `80%` of processed posts |
| Follow filter | follower/following counts differ by at most `5000` (follows only; likes and comments are never limited by it) |
| Comment rate | `50%` of processed posts |
| Comment deck | all 72 comments used once before any repeat |
| Comment engagement | likes up to `2` comments per post on `1` post of `3` followed accounts |
| Replies | `30%` of liked comments (count toward the comment caps) |
| Story watching | up to `5` followed accounts per run |
| Like cap | `25/hour`, `80/day` |
| Comment cap | `5/hour`, `15/day` |
| Follow cap | `10/hour`, `30/day` |
| Unfollow cap | `10/hour`, `30/day` |
| Unfollow check | not followed back within `3` days |
| Pause after a like | about `6–12` seconds |
| Pause after a comment | about `21–45` seconds |
| Pause after a follow | about `32–68` seconds |
| Long break | after every `4` hashtags, `2–4` minutes |
| Maximum run time | `45` minutes |
| Cooldown between runs | `3` hours (tracked separately per task) |
| Activity check | post published in the last `7` days |
| Concurrent runs | blocked by a lock file |
| Daily usage check | before the run and before every hashtag |

The hourly and daily caps are stored in InstaPy's SQLite database, so running
the script again on the same day **does not reset them**. When a cap is
reached, the run stops instead of continuing to hammer Instagram.

These defaults are conservative because the account in the existing logs
(`chekke_00`) appears to be new. Keep them for at least 1–2 weeks.

There are also hard safety ceilings that cannot be exceeded with command-line
flags: `--amount` ≤ 10, `--candidates-per-hashtag` ≤ 50, likes ≤ 50/hour and
200/day, comments ≤ 12/hour and
40/day, follows ≤ 20/hour and 80/day, unfollows ≤ 20/hour and 80/day. Extra
engagement is capped as well: `--like-comments-accounts` ≤ 10,
`--like-comments-posts` ≤ 3, `--like-comments-per-post` ≤ 5 and
`--story-accounts` ≤ 20. The defaults are well below these ceilings.

## Requirements

The project already has a virtual environment with InstaPy and Selenium:

```bash
cd /run/media/hope/hope/yoo/javascript/instapy-00
venv/bin/python --version
```

Firefox and geckodriver are required. The repository already contains fixes
for snap-packaged Firefox/geckodriver.

## Credentials and saved session

Use environment variables (safer than putting the password in shell history):

```bash
export INSTA_USER="your_username"
export INSTA_PW="your_password"
```

You can also pass them directly:

```bash
venv/bin/python hashtag_engagement.py --username your_username --password your_password
```

Do the first run **without** `--headless`. If Instagram asks for a verification
code, enter it in the Firefox window. InstaPy waits up to 5 minutes for it.

After that login, InstaPy saves the session cookie here:

```text
workspace/InstaPy/logs/<username>/<username>_cookie.pkl
```

Later runs reuse that cookie automatically and **do not need the password**:

```bash
export INSTA_USER="your_username"
venv/bin/python hashtag_engagement.py
```

You will see `Saved session found ...` in the output. The password is only
needed again if the session expires or you delete the cookie file. If a cookie
from an older `~/InstaPy` workspace exists, it is imported automatically.

## Preview without opening a browser

```bash
venv/bin/python hashtag_engagement.py --dry-run
```

This prints the hashtags, action rates and safety caps. It does not need
credentials and does not touch Instagram.

## Normal run

```bash
venv/bin/python hashtag_engagement.py
```

When you run it by hand, the script first asks what to do — no flags to
remember. See [Interactive setup](#interactive-setup) below. If you prefer the
old flag-only behaviour, add `--no-interactive`.

With the built-in list of 55 hashtags and `--amount 1`, one run can process at
most 55 posts. It will usually perform fewer actions because of the
percentages and caps. The 45 minute limit can stop a run before every hashtag
is reached. The script keeps a persistent rotating order in
`engagement_state.json`, so the next run continues with the hashtags that were
not reached instead of starting over. Use `--max-run-minutes 60` if you prefer
longer runs.

Before login, the script prints how much of today's quota is already used, for
example:

```text
Today's usage for 'your_username' before this run:
  likes    12/80   (68 left)
  comments 3/15    (12 left)
  follows  6/30    (24 left)
  unfollows 0/30   (30 left)
```

If any daily cap is already reached, the script refuses to start.

## Interactive setup

Run the script without any flag in a terminal and it asks you what to do. Every
question shows the current value in brackets, and pressing **Enter** keeps it,
so you only type the values you want to change:

```text
==============================================================
Interactive setup - press Enter to keep the value in brackets.
==============================================================

What should this run do?
  1. hashtags - like, comment on and follow posts under the hashtags
  2. unfollow - unfollow accounts that did not follow back in time
  3. comments - like comments on followed accounts and reply to some
  4. stories - watch stories of followed accounts
  0. every task
Choose tasks (e.g. 1,3 or 0 for all) [all]:
```

Type the task numbers separated by commas (for example `2,4` for unfollow and
stories), or press **Enter** / type `0` to run every task. The script then asks
only about the settings that matter for the tasks you picked — for example the
unfollow wait time is only asked when the unfollow task is selected — followed
by the shared safety caps, pacing and the headless question.

The answers are validated exactly like flags, so an impossible value (for
example a daily cap above the hard ceiling) stops the run with the same message
you would get from a flag.

The prompts are **skipped automatically** when they make no sense, so scripted
runs and previews keep working:

- `--dry-run` prints the current configuration and never asks.
- `--no-interactive` disables the questions even in a terminal (use this for
  cron or any automated job).
- If tasks were already chosen with flags (`--unfollow`, `--stories`, ...), the
  script does not ask.
- A non-terminal input (for example output piped to a file) never triggers the
  prompts.

## Running individual tasks

The work is split into independent tasks. You can pick them from the
[interactive menu](#interactive-setup), or pass flags if you prefer:

| Task flag | What it does |
| --- | --- |
| `--hashtags` | like, comment on and follow posts found under the hashtags |
| `--unfollow` | unfollow accounts that have not followed back within `--unfollow-after-days` |
| `--comments` | like comments on followed accounts' recent posts and reply to some |
| `--stories` | watch stories of followed accounts |
| `--all-tasks` | run every task together |

You may pass several flags to combine tasks in one run, for example only the
extra engagement:

```bash
venv/bin/python hashtag_engagement.py --unfollow
venv/bin/python hashtag_engagement.py --hashtags
venv/bin/python hashtag_engagement.py --comments --stories
venv/bin/python hashtag_engagement.py --all-tasks
```

In a terminal, **no** task flag means the script asks you what to run (press
Enter to choose every task). In a scripted or `--no-interactive` run, no task
flag means every task runs, so existing commands keep working. The cooldown is
tracked **per task**: running `--unfollow` ten minutes after a hashtag run is
allowed, because the unfollow task has its own last-run time. The daily caps are
still shared and are checked per task, so a task that has already used its cap
is skipped while the other selected tasks continue.

The rotating hashtag order in `engagement_state.json` is only advanced by the
hashtag task, so running `--unfollow` or `--stories` on their own does not
disturb the hashtag cycle.

## Hashtags and comments

The built-in hashtag list is grouped into four parts:

- Persian follow/like/comment exchange tags (the account's original niche),
- Persian growth and discovery tags,
- popular Persian content and lifestyle tags (`#ایران`, `#تهران`, `#عکس`,
  `#مد`, `#سفر`, `#طبیعت`, `#هنر`, ...),
- globally popular/trending tags (`#followforfollow`, `#likeforlike`,
  `#instagood`, `#photooftheday`, `#explorepage`, `#fyp`, `#viral`,
  `#reels`).

The script rotates through the whole list across runs, so the account reaches a
wider audience without dropping the follow-for-follow tags. You can still pass
your own list with `--tags-file`.

Comments are selected from a shuffled deck: every one of the 72 built-in
comments is posted once before any comment is repeated. This prevents the
"same comment everywhere" pattern that looks like spam. You can replace the
list with `--comments-file`; a larger list makes the no-repeat cycle longer.

## Extra engagement: stories, comment likes and replies

After the hashtag loop the script spends a little time on the accounts it
already follows. This keeps the account visible and encourages follow-backs:

- **Story watching** — `--story-accounts 5` (default) watches the stories of
  up to five followed accounts per run. Set it to `0` to disable.
- **Comment likes** — `--like-comments-accounts 3` (default) opens one recent
  post of three followed accounts and likes up to two comments on each.
  Set it to `0` to disable.
- **Replies** — `--reply-percentage 30` (default) replies to about 30% of the
  comments it liked. Replies mention the commenter and use the reply list
  (`--replies-file` to replace it). They count toward the normal comment caps.

All of these actions are small, use the same account and the same quota
supervisor, and are skipped if the daily cap is already reached or the run time
limit is hit. Disable everything with:

```bash
venv/bin/python hashtag_engagement.py \
    --like-comments-accounts 0 \
    --reply-percentage 0 \
    --story-accounts 0
```

If Instagram changes its page markup, comment likes or replies may find no
comments and simply skip that step; the hashtag like/comment/follow activity
continues normally. The step is wrapped so it cannot abort a run.

Features that depend on external services — Clarifai image checks, engagement
pods and MeaningCloud/Yandex sentiment analysis — stay disabled because they
need separate API keys. Everything that can run locally (like, comment, follow,
unfollow, story, comment-like and reply modules) is enabled.

## Follow filter and unfollows

The follower/following difference filter is applied to the **follow decision
only**. Before following an author, the script compares the account's follower
and following counts. If they differ by more than `--max-follow-difference`
(default `5000`), the author is not followed, but the post is still liked and
commented on. This keeps follows focused on accounts where a follow-back is
plausible without starving likes and comments.

> Earlier versions applied this filter to the whole post, so an account with a
> lopsided ratio was skipped entirely. Persian follow-for-follow hashtags are
> full of such accounts, which is why almost no like, comment or follow was
> performed. The filter can no longer block likes or comments.

At the start of each run the script also unfollows accounts it followed that
have not followed back within `3` days. Unfollowed accounts are written to
InstaPy's persistent follow-restriction table, so they are never followed again.

```bash
# default: follow when the difference is at most 5000
venv/bin/python hashtag_engagement.py

# stricter follow filter
venv/bin/python hashtag_engagement.py --max-follow-difference 1000

# ignore the follower/following ratio entirely for follows as well
venv/bin/python hashtag_engagement.py --max-follow-difference 0

# default: unfollow after 3 days
venv/bin/python hashtag_engagement.py

# give people more time to follow back
venv/bin/python hashtag_engagement.py --unfollow-after-days 7

# disable unfollowing
venv/bin/python hashtag_engagement.py --unfollow-after-days 0
```

Unfollows have their own hourly and daily caps and count toward the same daily
usage report as likes, comments and follows.

> **If a run reports `UNFOLLOWED 0 users` / `unfollows 0/30`,** check the log for
> `Retrieving live \`Followers\` data`. Instagram sometimes answers its private
> API with an HTML login/challenge page instead of JSON; when that happens the
> bot cannot build the list of non-followers and, to stay safe, unfollows
> nobody. The script now retries such a request from inside the logged-in
> browser (and logs the HTTP status, content type and a body snippet), so run
> the bot again and, if it still fails, wait a day — the block is on Instagram's
> side, not a missing 3-day threshold.

## Activity check (last week)

Before liking, commenting or following, the bot reads the post's publish date.
If the post is older than `7` days, the post is skipped completely — no like,
no comment and no follow — so only accounts that are still active get actions.
This also applies to the comment-liking step, so comments are only liked on
recent posts of recently active accounts.

```bash
# default: last 7 days only
venv/bin/python hashtag_engagement.py

# stricter or looser window
venv/bin/python hashtag_engagement.py --max-post-age-days 3
venv/bin/python hashtag_engagement.py --max-post-age-days 14

# disable the activity check entirely
venv/bin/python hashtag_engagement.py --max-post-age-days 0
```

If Instagram does not expose the post date, the post is skipped as well,
because the account's activity cannot be verified. Skipped posts are logged
with `Skipping '<user>'` and counted as skipped (not as inappropriate), and the
bot inspects the next candidate for the same hashtag instead of giving up.

Because the hashtag grids are usually ranked by engagement, many of the first
results can be old. The bot therefore inspects up to
`--candidates-per-hashtag` posts (default `5`) per hashtag until it handled the
requested `--amount` posts. This keeps a single stale post from wasting an
entire hashtag.

## Recommended routine

- Run at most **2–3 times per day**, at least 3 hours apart.
- Stop for the day once a cap is reached; do not raise the limits to "finish".
- After 1–2 weeks without warnings, you may increase limits gradually, for
  example:

```bash
venv/bin/python hashtag_engagement.py \
    --max-follows-daily 40 \
    --max-follows-hourly 12 \
    --max-comments-daily 20 \
    --max-comments-hourly 6
```

- Do not change your IP address or VPN location every run.
- Do not run the bot while you are also using the same account heavily on your
  phone.
- Keep the same workspace/database so the daily counters stay accurate.

## Useful options

| Option | Default | Meaning |
| --- | --- | --- |
| `--hashtags` | off | Run only the hashtag like/comment/follow task |
| `--unfollow` | off | Run only the unfollow task |
| `--comments` | off | Run only the comment like/reply task |
| `--stories` | off | Run only the story-watching task |
| `--all-tasks` | off | Run every task together (default when no task flag is given) |
| `--no-interactive` | off | Never show the interactive questions (for cron/scripts) |
| `--amount N` | `1` | Posts to process per hashtag |
| `--candidates-per-hashtag N` | `5` | Candidate posts inspected per hashtag until `--amount` posts are handled |
| `--tags-file FILE` | built-in list | One hashtag per line; replaces the built-in hashtags |
| `--comments-file FILE` | built-in list | One comment per line; replaces the built-in comments |
| `--replies-file FILE` | built-in list | One reply per line; used when replying to comments |
| `--reply-percentage N` | `30` | Percentage of liked comments that get a reply (`0` disables) |
| `--like-comments-accounts N` | `3` | Followed accounts whose posts are used to like comments and reply (`0` disables) |
| `--like-comments-posts N` | `1` | Recent posts inspected per account for comment engagement |
| `--like-comments-per-post N` | `2` | Comments liked per post |
| `--story-accounts N` | `5` | Followed accounts whose stories are watched per run (`0` disables) |
| `--follow-percentage N` | `80` | Percentage of processed posts whose author is followed |
| `--max-follow-difference N` | `5000` | Only follow accounts whose follower and following counts differ by at most N; likes and comments are never limited by it (`0` disables) |
| `--comment-percentage N` | `50` | Percentage of processed posts that receive a comment |
| `--max-likes-hourly N` | `25` | Hourly like cap |
| `--max-likes-daily N` | `80` | Daily like cap |
| `--max-comments-hourly N` | `5` | Hourly comment cap |
| `--max-comments-daily N` | `15` | Daily comment cap |
| `--max-follows-hourly N` | `10` | Hourly follow cap |
| `--max-follows-daily N` | `30` | Daily follow cap |
| `--unfollow-after-days N` | `3` | Unfollow accounts that have not followed back within N days and never follow them again (`0` disables) |
| `--max-unfollows-hourly N` | `10` | Hourly unfollow cap |
| `--max-unfollows-daily N` | `30` | Daily unfollow cap |
| `--max-run-minutes N` | `45` | Hard time limit for one run |
| `--max-post-age-days N` | `7` | Only interact with posts published in the last N days (`0` disables) |
| `--min-hours-between-runs N` | `3` | Cooldown between two runs |
| `--chunk-size N` | `4` | Hashtags processed before a long pause |
| `--chunk-pause-min N` | `2` | Minimum long pause in minutes |
| `--chunk-pause-max N` | `4` | Maximum long pause in minutes |
| `--include-top-posts` | off | Also interact with top posts |
| `--headless` | off | Hide the Firefox window |
| `--dry-run` | off | Print settings and exit |

For testing only, you can bypass the cooldown:

```bash
venv/bin/python hashtag_engagement.py --min-hours-between-runs 0
```

The hourly and daily caps still apply, so this will not make the account act
unboundedly.

## Custom hashtags and comments

Text files are UTF-8, one entry per line. Hashtags may include or omit `#`.
Persian characters, underscores, spaces and the Persian comma `،` are handled.
Empty lines are ignored; lines starting with `//` are treated as comments.

```bash
venv/bin/python hashtag_engagement.py \
    --tags-file my_hashtags.txt \
    --comments-file my_comments.txt
```

## Files created by the bot

All files live in `workspace/InstaPy/` inside this project:

- `logs/` — session logs and screenshots.
- `logs/<username>/<username>_cookie.pkl` — saved session used for later runs.
- `logs/<username>/commented_posts.txt` — posts this bot already commented on.
- `db/instapy.db` — action counters used for the hourly/daily caps.
- `engagement_state.json` — last run time per task (cooldown) and rotating hashtag order.
- `engagement.lock` — prevents two runs from using the account at once.

Do not delete `db/instapy.db` if you want the daily counters to keep working;
deleting it resets today's recorded usage and makes the caps less effective.

If the script reports `The saved session ... is no longer valid`, run once with
`INSTA_PW` (or `--password`) so InstaPy can log in and save a fresh cookie.

If the script was killed with `SIGKILL` or the machine lost power, a stale
`engagement.lock` may remain for up to one hour. Only delete it manually when
you are sure no other run is active.

## If Instagram blocks or restricts the account

If you see messages such as:

- "We restrict certain activity to protect our community"
- "Try again later"
- unexpected logouts, captchas or forced password resets

then immediately:

1. Stop the script and close the browser.
2. Do not retry every few minutes; that makes it worse.
3. Wait at least 24–48 hours without any automation.
4. Log in manually, use the account normally for a few days, then resume with
   lower limits (`--max-follows-daily 15`, `--max-comments-daily 8`).
5. If the block repeats, stop using automation on that account.
