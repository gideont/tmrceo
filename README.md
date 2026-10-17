# tmrCEO — tomorrow CEO

Children lead: Kaylie is Chief Imagination Officer and Owen is Chief Game Designer; the CEO role is open to multiple project leaders. Gideon provides adult support as Chief Engineer and remains a Board Member & Founding Investor. The homepage has a responsive Snake
game, team introductions, Firststone link, and opt-in newsletter signup.
The shared top-ten Snake board supports guest nicknames. Optional Google One Tap links nicknames and scores across devices.
Device best scores and nicknames stay in localStorage.

## Build and deploy

```sh
./1_build_docker.sh
./2_deploy_docker.sh
```

The `tmrceo-static` image/container name is retained. The Flask/Gunicorn server
maps host port **9002** to container port **8080**. Public HTTPS is handled by the
existing reverse proxy. Routes: `/`, `/firststone`, `/firststone/`, `/privacy`.
The old `nginx.conf` is retained as a reference and is no longer used in the image.

## Newsletter

Subscribers explicitly opt in. Email, consent timestamp/text, and a private
unsubscribe token are stored in SQLite on the **tmrceo-data** Docker volume.
Keep this volume when redeploying and include it in server backups. Unsubscribe
removes the subscriber row. No mail provider is configured; this app collects
signups and does not send email automatically.

Export subscribers locally when preparing an update:

```sh
docker exec tmrceo-static python export_subscribers.py > subscribers.csv
```

The CSV includes a per-recipient unsubscribe URL. Include that recipient’s link
in every newsletter. Keep the export private. This CSV is never served over HTTP.

## Edit and preview

Edit `index.html`, `styles.css`, or `snake.js`, then rebuild and deploy.
Snake uses a 20×20 grid and a 135 ms tick. Keyboard, swipe, direction buttons,
pause/resume, optional sound, and local best scores are handled in `snake.js`.

For a local preview, install requirements in a virtual environment and run
`./3_preview.sh` (port 8002). Preview signups use `/tmp/tmrceo-preview-data`.

## Firststone

The uploaded source is preserved in `firststone/` and the original ZIP.
After editing `firststone/article.html` or its hero image:

```sh
python3 firststone/build.py
./1_build_docker.sh
./2_deploy_docker.sh
```

Only its portable `index.html` is shipped. The optional product URL remains
unset as supplied; its final link points to its first-step exercise.

## The Tomorrow Times

The homepage newspaper sits after Snake. Its four initial articles were
published October 16, 2026. Edit `articles/stories.json` and regenerate with:

```sh
python3 articles/build.py
./1_build_docker.sh
./2_deploy_docker.sh
```

The generator updates the homepage newspaper between its markers and renders
four standalone pages. Article source links and image credits are visible on
each story. Original images and license references are in `assets/news/`.
Add new article slugs to the allowlist in `app.py` when adding more stories.

Discovery suggestions are saved privately in the `discoveries` table of the
same persistent SQLite database with `status=pending`. They are not automatically
published. Review them from the server; no public admin endpoint is exposed:

```sh
docker exec tmrceo-static python -c 'import app,json; c=app.db(); print(json.dumps([dict(r) for r in c.execute("SELECT * FROM discoveries ORDER BY submitted_at DESC")],indent=2)); c.close()'
```

Only publish a submission after reviewing its text, source, and permission.

## Leadership and adult supporters

This checkout uses static HTML/CSS and Flask, rather than Next.js/React.
Edit `leadership/members.json`: `leadership` holds children’s
profiles, and `board` holds adult supporters. Add entries to either array to grow
the team. Keep child IDs unique; supply a portrait filename from `assets/team/`.
The original Kaylie and Gideon illustrations are preserved as SVG files.
Board profiles expand using native HTML details, including without JavaScript.

After updating the member data or rendering component, regenerate the homepage:

```sh
python3 leadership/build.py
```

Commit the resulting `index.html` alongside the data and renderer. This matches
the existing article generator workflow. The generated leadership block is kept
separate from the newspaper block; either generator can be run independently.

The collapsed future fundraising preview uses `leadership/fundraising-demo.json`.
All four values are null placeholders, displayed as dashes, with a clear
**Demonstration data** label. They are not actual results or zero balances.
`render_fundraising(data)` in `leadership/build.py` is reusable with the same dict
shape from a future database query: total_funds_raised, available_funding,
active_investors, projects_funded, currency, and is_demo. Money values use major
currency units; supply an explicit three-letter currency code when adding values.
Keep `is_demo` true for sample values. Only use false with verified actual data.
No database connection, investment collection, or funding API is configured.

There is no package.json, JavaScript build or lint configuration.
Python compilation, Node syntax checks and Flask route smoke checks can be run
locally. Build/deploy scripts remain manual and unchanged.


## Open roles and role interest

Edit `open_roles` in `leadership/members.json` and run `python3 leadership/build.py`.
Multiple project CEOs are welcome. Kaylie is Chief Imagination Officer, Owen is Chief Game Designer,
and Gideon is Chief Engineer (adult support) as well as a board member. Owen uses
an illustrated initial/game-controller avatar until a portrait is supplied.
Expressions of interest are stored privately in SQLite’s `team_interest` table,
with `status=pending`, parent/guardian contact and permission. They do not assign
roles, send emails or subscribe applicants to the newsletter. Review locally:

```sh
docker exec tmrceo-static python -c 'import app,json; c=app.db(); print(json.dumps([dict(r) for r in c.execute("SELECT * FROM team_interest ORDER BY submitted_at DESC")],indent=2)); c.close()'
```

Keep submissions private and follow up through the parent or guardian. The
contact email is not published. Review and remove unneeded submissions manually.

## Books and reader likes

Edit `books/books.json`, add a matching JPEG under `assets/books/`, then run
`python3 books/build.py`. The shelf encourages library borrowing and sharing with friends; it contains no publisher or shop links.
`assets/books/CREDITS.md` records cover sources and edition ISBNs. The six picks are the family’s original choices. Source links remain only in
the private registry and cover-provenance notes, not on the public bookshelf.

Reader likes are real counts, initially zero, stored in the existing persistent
`tmrceo-data` volume. A random 180-day HttpOnly/SameSite cookie identifies this
browser’s choices; only its hash is stored. Repeating a like doesn’t add another
vote, and unliking removes it. Counts represent browser choices, not verified
unique people. No accounts, email addresses or advertising tracking are used.

Article records require `author` and `date`. The generator displays these on
homepage cards and standalone posts. Current posts retain the existing newsroom
credit. For approved discoveries, use the contributor’s chosen public credit
(or an anonymous credit if no name was supplied), actual publication date and
source links. Review and proofread for accuracy and suitability before publishing.

Run the standard-library regression suite with the project requirements installed:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile app.py leadership/build.py books/build.py articles/build.py
node --check community.js
node --check snake.js
```

Regenerate the homepage sections independently before building/deploying:
`python3 leadership/build.py`, `python3 articles/build.py`, `python3 books/build.py`.
The container includes the member/book registries for API validation; new roles
or books require the usual manual image rebuild and container restart.


## Feature tracker

The standalone `/features` page is linked before Firststone in navigation and the
footer, plus a small homepage panel directly above the Firststone section. Its queue/history is
not embedded on the homepage. It has a noindex tag and no authentication; it is
a normal public page reached through a link or its URL.

Edit `features/features.json`, then run:

```sh
python3 features/build.py
```

Each feature has a unique `id`, `title`, `description`, and a `status` of `queued`
or `shipped`. For shipped work, supply the actual `completed_on` date in
YYYY-MM-DD format. To record progress, update the status and date, or append a
new entry for a later improvement to preserve history. The renderer lists queued ideas first, then completed work in compact task rows
with short descriptions, requested/completed dates and Gantt bars.
Commit the generated `features/index.html` and rebuild/deploy manually as usual.

Manual speed selection remains queued. Candy acceleration, custom snake colours and rainbow mode are available.
The guest leaderboard and browser-remembered gamer names are now implemented.

Open roles now use playful labels. Internal IDs for the existing marketing,
communications, game and newsroom roles are retained so stored interest records
remain meaningful. CFO and FP&A are removed from the current choices; existing
submissions remain stored. The Book Explorer role is new. Each project can have
its own CEO; the interest form does not enforce a single occupied CEO seat.


### Gantt sample dates

The Gantt table uses a small “Sample dates” caption instead of a banner. Its
example spans show a quiet early October and more work completing October 12–16,
with different calendar durations. Recorded `requested_on` and `completed_on`
remain separate and unchanged. Presentation-only fields are
`timeline_date_basis: "sample"`, `timeline_requested_on`, and
`timeline_completed_on` (null for queued work). Keep the sample caption while
showing example dates. Replace these with verified dates when supplied.

The queue has request markers and “Not yet” for completion, with no invented
future deadlines. Bars span requested-to-completed calendar dates, not effort.
The chart uses HTML/CSS and accessible tables, scrolls horizontally within the
page on narrow screens, and adds no dependencies. Run `python3 features/build.py`
after edits.


Early groundwork includes owner-supplied brainstorming, domain registration and
web hosting. Exact historical dates were not supplied, so recorded date fields
are null and sample timeline fields supply the chart positions. The owner confirmed that project email is already set up, so it is completed.
This is separate from automated newsletter sending, which remains unconfigured.


## Guest arcade leaderboard

`arcade.js` handles nicknames, the returning-player greeting, and the top-ten
scoreboard. New players are prompted after a finished game, can skip sharing,
and can change their nickname later. `tmrceo-snake-name` in localStorage keeps
it on this browser. A one-year HttpOnly/SameSite guest cookie identifies the
server player; only its hash is stored. This is a guest identity, not an account
or a unique real person. Optional Google sign-in attaches guest progress to an
account without exposing the cookie or requiring a real name.

Snake tables live in `/data/games/snake.sqlite3` inside the existing persistent Docker volume. The board shows the ten highest individual round scores, allowing the same nickname in multiple positions. Ties go to the earlier score. Renaming preserves that score. Empty
positions are labelled OPEN SPOT. No sample players or imported device-only
scores are published. Skipping the nickname keeps the game playable and does
not publish the score. Existing local best scores are retained on the device.

Each online round gets a server-issued seed and run ID. `snake.js` records the
per-tick directions; `snake_rules.py` replays the same food generation and rules
on submission, requires a finished legal game, and checks a minimum elapsed time using the same candy-by-candy speed curve as the browser.
Submitted numeric scores are not trusted. Runs expire after two hours. This is
basic checking for a casual guest board, not proof of a unique person or a
cheat-proof competition. Nicknames are limited to 2–20 letters/numbers and simple
punctuation and are inserted into the UI as text. The UI discloses that the name
and qualifying round scores will be public before saving. No email is required.

An unavailable server does not prevent playing; device best scores still work.
Pending online rounds can be retried during the current visit. The server does
not retain move strings after checking them. The current speed remains 135 ms;
future speed controls will need corresponding server rule changes.


## Terms of Use

`terms.html` serves at `/terms` and `/terms/`, with public contact
`gideon@gmail.com` supplied by the owner. It covers families, fair play and guest
scores, contributions/credit, project roles, content rights, privacy links,
availability, updates and contact. The homepage, article pages, feature tracker,
privacy page and Firststone link to it. Update the visible revision date whenever
terms change. The source remains a plain editable HTML file, with no dependencies.

No legal business identity or governing jurisdiction was supplied, so the page
does not invent either. This is a starting set of terms for the current site;
qualified legal review remains appropriate before relying on it as a contract.
Terms do not establish or verify parental consent. The page does not claim that
posting terms makes the existing child-facing sharing features compliant with
privacy law. Consent requirements and actual feature behavior need separate review.
Reference guidance consulted: https://www.ftc.gov/business-guidance/resources/complying-coppa-frequently-asked-questions
and https://www.priv.gc.ca/en/privacy-topics/privacy-for-businesses/appropriate-handling-of-personal-information/collecting-personal-information-and-consent/consent/gl_omc_201805/


The homepage introduction is compact. `.game-layout` groups `.game-play-area`
and the narrow top-ten column inside the same `.game-card`. At widths above
700px they sit side by side; at mobile widths they stack within that card.
The game IDs and JavaScript behavior are unchanged by this layout.


## Google Identity Services

This deployment is Flask/Gunicorn, not Next.js. The requested environment name
`NEXT_PUBLIC_GOOGLE_CLIENT_ID` is retained: it is a public web client identifier,
read server-side and returned by `/api/auth/session` to initialize GIS.

Create a host-only `.env` from `.env.example`, set the web client ID, and restrict
permissions with `chmod 600 .env`. The deploy script passes it at runtime;
Docker excludes environment files from its build context. Never add a client
secret or ID token to frontend code. No OAuth client secret is needed for this
ID-token flow. `AUTH_ALLOWED_ORIGINS` defaults to the two production HTTPS origins.
Local authentication previews also require HTTPS and an explicitly allowed origin.

In Google Cloud Console, open this **Web application** OAuth client and add
`https://tmrceo.com` and `https://www.tmrceo.com` as Authorized JavaScript origins.
Configure consent branding with the homepage, `/privacy` and `/terms`. If Google
keeps the app in testing mode, add the intended test accounts or complete the
appropriate publishing process. The JavaScript callback flow needs no redirect
URI. Test once with a real Google account after this configuration. Browser
settings and Google's prompt cooldown may suppress One Tap; the official Sign in
with Google button remains available. See [Google setup documentation](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid).

`auth.js` loads only the official GIS SDK and sends ID tokens in HTTPS POST bodies.
`google_auth.py` uses Google's verifier with cached public certificates and checks
signature, audience, issuer, expiry and a browser-bound nonce. Login and logout
also require exact allowed origins and CSRF tokens. Sessions are opaque random
values in Secure, HttpOnly, SameSite=Lax `__Host-` cookies, expire after seven days,
and are revocable on logout. SQLite stores only session hashes. The persistent
volume adds `auth_users`, `auth_sessions` and short-lived `auth_challenges` tables.
Accounts store Google's unique `sub` and a verified email privately for game logs; Google names are not stored. ID tokens are
never persisted. Guest nicknames and best scores merge on login, retaining the
account's chosen nickname and the best score. Unfinished guest runs transfer too.
Logout ends this browser's session; it does not delete the account or sign out of
Google itself. Session and challenge expiry cleanup runs on session requests.

Run `/tmp/tmrceo-leadership-venv/bin/python -m unittest discover -s tests -v`
(or your own virtualenv with `requirements.txt` installed). Auth tests use RSA-signed
fixtures and an isolated test certificate, including signature rejection, nonce,
CSRF, expiry, logout revocation and cross-browser guest merging. A real Google
account check remains necessary; fixtures do not validate Cloud Console settings.
Build with `./1_build_docker.sh` and deploy with `./2_deploy_docker.sh`.
Nginx must preserve Host and X-Forwarded-Proto, and proxy to localhost:9002.
The app sends `Cross-Origin-Opener-Policy: same-origin-allow-popups` for GIS popups.


## Pixel Snake customisation and speed

The board is a 200×200 canvas with nearest-neighbour scaling. Sprites are original
square pixel drawings; there are no external game assets or new dependencies.
A colour picker, preset swatches and rainbow mode update the snake immediately.
The selection is saved locally as `tmrceo-snake-colour`, independently of sign-in.
Candy still awards 10 points. Each candy reduces the next movement delay using
`ceil(45 + 90 / (1 + 0.18 * candies))` milliseconds, starting at 135ms and tending
toward 45ms. The speed display, restart and pause/resume use the current delay.
`snake_rules.py` sums those same delays during replay instead of assuming a fixed
speed, so legitimate faster games can still submit scores. Existing slower
browser sessions remain valid. Score values and the existing leaderboard persist.


## News curiosity cards

`news_quiz.py` holds the editable question registry, server-side answer checks and
HTML renderer used by `articles/build.py`. Each question links to its published
clue: a news article or the sourced mudroom word story inside the newspaper.
Run `python3 articles/build.py` after editing quiz copy, then
`python3 features/build.py` if you also update the feature tracker.

`news-quiz.js` records the first answer only, including guest answers and incorrect answers. Signed-in
accounts earn 10 private curiosity points per correct question, once per question.
The `quiz_rewards` SQLite table has a unique `(user_id, question_id)` key, so
retries and concurrent submissions cannot duplicate rewards. Totals are computed
server-side, separately from Snake scores. Authenticated submissions require the
existing session CSRF token and an allowed origin. GET progress is private and
uncached. Add new immutable question IDs for new rewards; do not reuse a rewarded
ID for a different question. Rewards remain in the persistent data volume.
Sign-in/logout controls now sit above the main content; the game has no account
explanation banner. Avatar, admin and article-authoring settings remain future work.


## Arcade round rankings

`snake_scores` stores each validated round by unique run ID, player ID, score and
achievement time, independently of the temporary `snake_runs` replay records.
The top ten ranks rounds, allowing one player to occupy all ten positions.
Repeated submissions of a run cannot create additional entries. Personal bests
are still kept in `snake_players`, and guest-to-Google merges transfer every
score without deduplicating different rounds. Renaming updates the displayed
name on all of that player's entries. Quiz curiosity points remain separate.

The transactional `arcade-rounds-v1` migration preserves each existing player's
stored best once; earlier individual rounds were not recorded and cannot be
reconstructed. The migration marker prevents later personal-best changes from
creating additional legacy entries. Round scores survive the two-hour replay
cleanup. Existing deployment backups allow rollback of the service and data.


The arcade header now says “Let’s play Snake!” with the returning-player greeting
at the right. On larger screens, colour controls form a narrow vertical rail beside
the board; scores, speed and sound sit above the top-ten table. On small phones,
colour controls wrap below the board to preserve its width. On single-column
layouts the game appears before the project introduction, bringing play upward.


## High-score celebrations

Score receipts include the rank of that exact round, using the same score/time/run-ID
ordering as the public leaderboard. `arcade.js` celebrates only successfully saved
rounds in positions 1–10, not a personal-best comparison or an existing record on
page load. First place gets a larger trophy and confetti celebration; other top-ten
rounds get their exact rank. Repeated callbacks for a round celebrate once per visit.
A failed score submission does not celebrate. The native dialog supports Escape,
keyboard focus, a Keep playing button and a Quit button that closes without starting another round. It pauses an active game if a delayed
score save completes during the next round. Reduced-motion preferences disable
confetti and bouncing. Synthesized claps and a short fanfare use the existing sound
toggle; a muted player may choose Play applause. Closing the dialog or hiding the
page stops the celebration audio. No audio files or new dependencies are required.


## Per-game persistent SQLite storage (October 17, 2026)

All files below live on the existing `tmrceo-data:/data` volume:

- `/data/newsletter.sqlite3`: shared accounts, sessions and community features.
- `/data/games/snake.sqlite3`: Snake profiles, replay runs, individual scores and
  `snake_play_log(run_id, player, username, email, play_starttime_epoch, score,
  finished_at, source)`.
- `/data/games/curiosity.sqlite3`: first-answer attempts and curiosity rewards.

`game_storage.py` attaches each game file to the shared SQLite connection, allowing
account merges to commit atomically across the files using SQLite's rollback
journals. Keep these databases on the same local persistent volume and do not
switch individual attached files to WAL without reviewing cross-file atomicity.
Existing game rows are moved transactionally out of the shared database once;
existing scores, rewards, accounts and sessions are preserved. Back up all files
when making future upgrades. For rollback to old code, restore the pre-upgrade
shared database and remove the newly migrated game files while the service is
stopped; do not run the old and new writers together.

Every accepted Snake start creates one private log row. Its `score` is NULL until
a legal completed replay is submitted; an unnamed round is logged privately and
can be published after a nickname is saved. Repeated submissions do not create
new plays or overwrite a checked score. Guest emails are NULL. Existing accounts
whose emails were never stored receive an email only after their next Google
sign-in supplies `email_verified: true`. No emails are exposed by the public API.
Old recorded rounds retain scores; missing historical start times remain NULL.
`source=legacy_best` identifies an old best whose originating run cannot be
reconstructed and excludes that entry from the play counter to avoid counting
it twice. Other historical records are the known baseline, not an invented total
for unrecorded earlier games. Replay cleanup never deletes the permanent logs.

`/api/snake/stats` reports recorded starts and distinct player identities. An
identity is a Google account or guest browser; sign-in merges that guest's logs
into its account so player counts can decrease as duplicates are recognized.
These statistics are independent of the public top-ten scores and quiz points.

“Do you know?” records one first answer per question per account or guest cookie.
The server uniqueness constraint, not just disabled buttons, prevents retries.
Wrong answers remain locked. Guest attempts transfer on sign-in without replacing
an existing account attempt; newly transferred correct answers earn points once.
Old rewarded questions migrate as correct locked attempts. Clearing cookies can
create a new guest identity; account limits persist across browsers. Each new
question needs a new immutable ID. **Automatic daily question rotation is pending**;
there is no midnight reset or daily claim on the current questions.


## High-score record details

The More button below the compact top-ten board opens a native dialog with the
current No. 1, its score-set time and live unbeaten duration, plus one score-set date for each of the ten rounds. `/api/snake/leaderboard/details` reads the same
score ordering as the board. It exposes names, scores and score-set dates only,
never email addresses, private game-start logs or internal IDs.
Dates display in the viewer's local timezone, identified in the dialog. The
unbeaten counter starts from the server's elapsed duration and advances with a
monotonic browser clock; a Refresh button checks for newer records. Equal scores
leave the earlier round on top and do not reset the standing time. Missing historical score dates say Not recorded. Opening the record book pauses active
play, and keyboard scrolling inside the dialog cannot resume the game. The
record data is derived from persistent Snake scores and survives container restarts.

The record book shows one arcade timestamp per round: when the score was set.
The original play-start epoch remains in the private game log for usage records.
