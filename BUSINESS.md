# BUSINESS.md

Requirements for Moodometer, in service of the red-green-refactor flow
described in `AGENTS.md`/`CLAUDE.md`. Every `REQ-<AREA>-<N>` below is
checked against INCOSE well-formedness (see `CLAUDE.md`'s Requirements
section) before `requirement-specialist` turns it into a failing test —
each one here has already been written to pass that check: single
testable statement, no vague qualifiers, no open TBD.

These requirements describe the behavior the running application (`app.py`
and its imports) is meant to have, derived from what's actually
implemented and constrained in `models.py`/`schemas.py`/`auth.py`. Where
the code doesn't yet conform, that's tracked under "Known Defects," not
smoothed over. Where intended behavior is genuinely ambiguous, that's
under "Open Questions" rather than guessed into a REQ.

## Authentication

- **REQ-AUTH-1**: `POST /auth/login` shall return 200 with a bearer
  `access_token` and `token_type: "bearer"` when the submitted username
  and password match a stored user's bcrypt-hashed password.
- **REQ-AUTH-2**: `POST /auth/login` shall return 401 with a
  `WWW-Authenticate: Bearer` header when the username does not exist or
  the password does not match.
- **REQ-AUTH-3**: An issued access token shall expire 30 minutes after
  issuance and shall be rejected by protected endpoints once expired.
- **REQ-AUTH-4**: A user's password shall be stored only as a bcrypt
  hash; the plaintext password shall never be persisted.
- **REQ-AUTH-5**: Any endpoint that depends on `get_current_active_user`
  shall return 401 when the request's Authorization header is missing,
  malformed, or carries an invalid or expired token.

## User Accounts

- **REQ-USER-1**: `POST /users` shall create an account given a username
  of 3–50 characters and a password of at least 8 characters, returning
  201 with the created user's `id`, `username`, and `created_at` (no
  password field in the response).
- **REQ-USER-2**: `POST /users` shall return 400 when the requested
  username is already registered.
- **REQ-USER-3**: `PUT /users/{username}` shall update only the
  authenticated caller's own password, returning 403 when the caller's
  username differs from `{username}`.
- **REQ-USER-4**: `DELETE /users/{username}` shall delete only the
  authenticated caller's own account (403 otherwise), return 204 on
  success, and cascade-delete that user's moods and entries.
- **REQ-USER-5**: `GET /users/{username}/full` shall return the target
  user's profile together with all of their moods and entries, and shall
  return 403 when the authenticated caller's username differs from
  `{username}`.
- **REQ-USER-6**: `GET /users/{username}` shall require the caller to be
  authenticated (401 without a valid token), and shall return the target
  user's `id`/`username`/`created_at` for any authenticated caller — it is
  not restricted to the caller looking up their own username (that
  restriction is what `/full` is for). Resolves OQ-1 below.

## Moods

- **REQ-MOOD-1**: `POST /users/{username}/moods` shall create a mood
  entry for the authenticated caller (403 if the caller's username
  differs from `{username}`) with `energy` and `valence` both required
  and each constrained to the closed interval [-1.0, 1.0].
- **REQ-MOOD-2**: A created mood's timestamp shall default to the current
  UTC time when the caller does not supply one.
- **REQ-MOOD-3**: `GET /users/{username}/moods` shall return only the
  authenticated caller's own moods (403 otherwise), ordered newest-first,
  paginated via `skip`/`limit` (`limit` defaulting to 100).
- **REQ-MOOD-4**: `GET`, `PUT`, and `DELETE` on
  `/users/{username}/moods/{mood_id}` shall return 404 when no mood with
  that id exists for that user — whether the id doesn't exist at all, or
  belongs to a different user.
- **REQ-MOOD-5**: A mood entry shall accept an optional `notes` field of
  up to 1000 characters, persisted and returned unchanged on creation and
  update.

## Journal Entries

- **REQ-ENTRY-1**: `POST /users/{username}/entries` shall create a
  journal entry for the authenticated caller (403 otherwise) with
  `content` required, 1–5000 characters.
- **REQ-ENTRY-2**: A created entry's timestamp shall default to the
  current UTC time when the caller does not supply one.
- **REQ-ENTRY-3**: `GET /users/{username}/entries` shall return only the
  authenticated caller's own entries (403 otherwise), ordered
  newest-first, paginated via `skip`/`limit` (`limit` defaulting to 100).
- **REQ-ENTRY-4**: `GET`, `PUT`, and `DELETE` on
  `/users/{username}/entries/{entry_id}` shall return 404 when no entry
  with that id exists for that user.

## Analytics

- **REQ-ANALYTICS-1**: `GET /users/{username}/analytics/statistics` shall
  return, for the authenticated caller's own moods only (403 otherwise),
  the entry count, timestamp range, and mean/median/stdev/min/max for
  both energy and valence, optionally filtered to a `start_date`/
  `end_date` window.
- **REQ-ANALYTICS-2**: `GET /users/{username}/analytics/patterns` shall
  report time-of-day averages, day-of-week averages, a volatility
  classification (low/moderate/high), and streaks of 3 or more
  consecutive same-quadrant moods, computed over the trailing `days`
  query parameter (default 30), for the authenticated caller's own moods
  only (403 otherwise).
- **REQ-ANALYTICS-3**: `GET /users/{username}/analytics/patterns` shall
  report `patterns_detected: false` with an explanatory message, rather
  than computing patterns, when fewer than 7 moods fall in the requested
  window.
- **REQ-ANALYTICS-4**: `GET /users/{username}/analytics/insights` shall
  return a list of human-readable insight strings derived from the
  authenticated caller's own mood statistics and patterns (403 for other
  users).

## Data Export

- **REQ-EXPORT-1**: `GET /users/{username}/export/csv` shall return the
  authenticated caller's own moods (403 otherwise) as a downloadable CSV
  attachment, one row per mood, containing the fields that exist on a
  mood entry: timestamp, energy, and valence. (See Known Defects: KD-1 —
  the current implementation does not conform.)
- **REQ-EXPORT-2**: `GET /users/{username}/export/json` shall return the
  authenticated caller's own moods, and optionally entries
  (`include_entries=true`), as a downloadable JSON attachment, filterable
  by `start_date`/`end_date`. (See KD-1.)
- **REQ-EXPORT-3**: `GET /users/{username}/export/pdf` shall return a PDF
  report containing the caller's mood statistics and their most recent
  mood history. (See KD-1.)
- **REQ-EXPORT-4**: All three export endpoints shall accept optional
  `start_date`/`end_date` query parameters in `YYYY-MM-DD` format and
  return 400 for a value that fails to parse as that format.

## Known Defects

Not new requirements — tracked non-conformance against the requirements
above, so the red-green loop has a concrete target.

- **KD-1**: `export_moods_csv`, `export_moods_json`, and
  `export_moods_pdf` in `app.py` read `mood.mood` off `MoodModel`, and
  `entry.mood` off `EntryModel`. Neither model defines those attributes.
  `mood.notes` is no longer part of this defect — `MoodModel` gained a
  real `notes` column (REQ-MOOD-5) — but `mood.mood` (a quadrant label)
  and `entry.mood` (which needs an entry-to-mood link that doesn't exist
  yet — see REQ-ENTRY-5/6) still don't exist on the models. Exporting any
  non-empty mood or entry list still raises `AttributeError` at request
  time. REQ-EXPORT-1/2/3 describe the corrected behavior: `mood.mood`
  should be the quadrant label derived from energy/valence (not a stored
  column), and `entry.mood` should come from the entry's linked mood, if
  any.

## Open Questions

Requirements blocked on disambiguation — per the well-formedness check in
`CLAUDE.md`, these are not written as `REQ-*` until answered, because
guessing the answer risks locking in the wrong access rule.

- ~~**OQ-1**~~ — resolved: `GET /users/{username}` shall require
  authentication (any authenticated caller, not self-only). See
  REQ-USER-6. `app.py`'s `get_user` does not yet conform (no auth
  dependency currently) — closing that gap is this requirement's
  red-green step.

## Backlog (not yet requirements)

From the README's roadmap — listed here so they aren't lost, but each is
currently too vague to pass the well-formedness check and needs a
specific, verifiable acceptance statement before `requirement-specialist`
can turn it into tests (a breakpoint/viewport definition for
"mobile-responsive," a latency bound for "real-time," a named
provider/protocol for "calendar integration"):

- Mobile-responsive design improvements.
- Real-time mood updates (WebSockets).
- Calendar integration.
