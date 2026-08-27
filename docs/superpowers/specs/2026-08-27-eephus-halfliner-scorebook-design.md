# Eephus Halfliner Scorebook — Design

## Background

This project started as a Cubs-only scorebook ("Numbers Game #22"): `scorebook.html`
and `scorebook.py` both hardcode `TEAM_ID = 112` and prefill/track exactly one
team's games, pulled live from `statsapi.mlb.com`.

This fork generalizes the tool to any MLB team and adds three new data points
(end time, attendance, weather). It rebuilds `scorebook.html` and `scorebook.py`
in place — the Cubs-only, Numbers-Game-#22 version does not continue to exist
as a separate product. The rebuilt tool is the **Eephus halfliner scorebook**.

All existing spoiler-safety behavior (no scores, no linescore, hidden
substitutions behind a per-game reveal) carries forward unchanged — this design
only adds team selection and the three new fields.

## 1. Picker page (`index.html`)

Replaces the current auto-redirect-to-Cubs behavior. Becomes the landing page:

- A date picker, defaulting to the visitor's local today (browser's local date,
  not a fixed timezone).
- Fetches `/api/v1/schedule?sportId=1&date=YYYY-MM-DD&hydrate=team,venue` — every
  MLB game on that date, no team filter.
- Lists each game: away @ home, first-pitch time (venue-local + viewer's local),
  ballpark name. **No scores, no live status beyond a plain Scheduled/Live/Final
  label** — consistent with the project's no-spoilers rule. A picker is still
  a picker even for a game you're avoiding results for.
- Clicking a game navigates to `scorebook.html?gamePk=XXXXX`.

## 2. Detail page (`scorebook.html`)

- Drops `TEAM_ID` and the "find today's Cubs game, else fall back to the next
  one within 10 days" lookup entirely.
- The page now loads exactly one game, identified by `?gamePk=` in the URL.
  There is no other supported entry point — old team-based bookmarks/links do
  not carry forward, since `gamePk` is what the picker hands off and a
  team+date pair is ambiguous once any team is in scope (a date can have up to
  ~15 games).
- Every downstream feature (lineups, starting pitchers, managers, umpires,
  substitutions, spoiler-hiding, per-game "Show moves" reveal) is unchanged —
  it's already keyed off the game object, not the team.

## 3. New data fields

Confirmed against the live MLB Stats API feed (`/api/v1.1/game/{gamePk}/feed/live`)
on 2026-08-26:

| Field | Source | Notes |
|---|---|---|
| Attendance | `gameData.gameInfo.attendance` | Present once posted (observed populated on a Final game); absent/pending before then |
| End time | `gameData.gameInfo.firstPitch` + `gameData.gameInfo.gameDurationMinutes` | Only computable once the game is Final (duration isn't known before then) |
| Actual weather | `gameData.weather.condition` + `gameData.weather.temp` | Populated live/post-game |
| Forecast weather | Open-Meteo (`api.open-meteo.com`, free, no key) hourly forecast, keyed on `venue.location.defaultCoordinates` (lat/long) and the game's first-pitch hour | Used only pre-game; no key/account needed, matching the project's "no key, no account" philosophy |

### Roof handling

`venue.fieldInfo.roofType` gives `Open`, `Retractable`, or `Dome` (confirmed
against Comerica Park = `Open` and Chase Field = `Retractable` on 2026-08-26).

- **`Dome`** — always display **"Domed"**, both pre-game and post-game. No
  Open-Meteo call is made for these venues at all.
- **`Retractable`** — pre-game: show the Open-Meteo forecast (roof state isn't
  knowable ahead of time). Live/post-game: use MLB's own `weather.condition`
  directly. Confirmed that MLB already self-reports `"Roof Closed"` as the
  condition string when the roof is shut (Chase Field, 2026-08-26 game), so no
  extra roof-state branching is needed once actual data is available.
- **`Open`** — forecast pre-game, actual weather post-game/live, same as today's
  Wrigley-only behavior conceptually, just now driven by `roofType` instead of
  being implicitly true for the one hardcoded park.

### Display cutover (forecast vs. actual)

Driven by game status, matching how the rest of the page already treats
pregame vs. in-progress/final state:

- **Preview/Scheduled** → forecast weather; attendance and end time not shown
  (not yet knowable).
- **Live/In Progress or Final** → actual weather if `gameData.weather` is
  present, attendance if `gameInfo.attendance` is present, end time only once
  the game is Final (needs `gameDurationMinutes`, which isn't set until the
  game ends).

## 4. CLI (`scorebook.py`)

- Adds `--team CHC` (abbreviation) / `--team-id 112` and `--game-pk N` flags
  for direct selection, replacing the hardcoded `TEAM_ID`.
- With no game-selecting flag passed, prints today's games numbered and
  prompts interactively for a selection — mirroring the HTML picker instead of
  defaulting to a single hardcoded team.
- Gains the same three new fields (end time, attendance, weather), computed
  the same way as the HTML tool, printed in the pregame header block. Needs
  its own Open-Meteo call for forecast weather, using the same venue
  coordinates + roofType logic described above.
- A small static team abbreviation/ID lookup table is needed to resolve
  `--team CHC` to a team ID (the picker doesn't need this, since it lists all
  games directly from the schedule endpoint without filtering by team).

## 5. Branding

- A small lookup table of each MLB team's primary/secondary color (hex),
  keyed by team ID, replaces the hardcoded Cubs blue/red CSS variables.
- The detail page recolors its header to the **home team's** colors for
  whichever game is loaded.

## 6. Renaming

- Since this rebuilds the tool in place, all "Cubs Scorebook" / "Numbers Game
  #22" branding in page titles, the README, and CLI help text is replaced with
  language describing the Eephus halfliner scorebook and its any-team,
  any-date behavior.
- The README section documenting the no-scores/hidden-moves philosophy stays
  intact conceptually but gets reworded away from Cubs-specific phrasing
  ("Cubs game", "CHC") to generic team language.

## Out of scope

- Historical seasons / postseason-specific behavior beyond what the existing
  schedule endpoint already returns.
- Minor/spring-training games (`sportId=1` only, matching current behavior).
- Any change to the substitution-tracking, spoiler-reveal, or caching logic
  beyond what's needed to key it off `gamePk` instead of `TEAM_ID`.
