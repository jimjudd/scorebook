# Eephus Halfliner Scorebook

Everything needed to fill out an **Eephus halfliner** scorebook — the header before
first pitch, and every substitution once the game is underway — for any MLB game on
any date. Pulled from MLB's public Stats API, plus a free Open-Meteo call for
pregame weather forecasts. No key, no account.

## Picking a game

`index.html` is the landing page: a date picker (defaults to your local today) and
every MLB game scheduled that day, with first-pitch time and ballpark. No scores or
live state beyond a plain Scheduled/Live/Final label — a picker is still a picker
even for a game you're avoiding results for. Click a game to open it in
`scorebook.html`.

## Before first pitch

| Field | Where it comes from |
|---|---|
| Batting order, positions, jersey numbers | `boxscore` → per-player `battingOrder` + `allPositions` + `jerseyNumber` |
| Starting pitchers (number & hand) | `gameData.probablePitchers` |
| Managers | `/teams/{id}/coaches` → `jobId: MNGR` |
| Team records | `gameData.teams[side].record` |
| HP / 1B / 2B / 3B umpires | `boxscore.officials` |
| First pitch (venue-local + your time) | `gameData.datetime` + venue timezone |
| Ballpark | `gameData.venue.name` |
| Weather forecast (pregame) | Open-Meteo, keyed on venue coordinates + first-pitch hour |

## No scores, ever

**This tool never shows the score, the inning, or anything about how a game is
going.** It doesn't even ask the API for the linescore. That's deliberate — the
point is to fill out a scorebook, and if you record games to watch later, a score
on the page ruins them.

In-game moves are spoilers too — a starter pulled in the 3rd, five relievers by
the 6th, or a position player pitching all tell you exactly how it's going. So
they're **hidden by default**:

- **On the page:** a "Show moves" button appears when there's something to reveal.
  Your choice is remembered **per game** — revealing at the ballpark does *not*
  un-hide a different game you're planning to watch on tape.
- **In the CLI:** pass `--show-moves`.

With moves hidden you still get the full prefill: lineups, positions, jersey
numbers, both starting pitchers, managers, records, umpires, first pitch, park.

## Once the game is underway or final

| Field | Notes |
|---|---|
| Attendance | Appears once MLB posts it — typically once the game is Final |
| End time | Only computable once the game is Final (duration isn't known before then) |
| Actual weather | Domed parks always show "Domed"; retractable-roof parks show MLB's own reported condition, which already says "Roof Closed" when shut |

Every substitution, in order, with the inning it happened:

| Move | Shown as |
|---|---|
| Pitching change | `B7 CHC P Trent Thornton #49 relieves Aaron Civale` |
| Pinch-hitter | `T6 CHC PH Tyrone Taylor #55 for Michael Conforto (slot 8)` |
| Pinch-runner | `PR`, same shape |
| Defensive substitution | `B8 CHC DEF Kevin Alcántara #13 for Pete Crow-Armstrong (slot 1)` |
| Position switch | `B6 CHC SWAP Tyrone Taylor moves to DH` |

Substitutions also appear **indented under the batting slot they entered**, so a
slot's whole chain reads top to bottom the way you'd pencil it in:

```
8   20  Michael Conforto     D DH   L
    55  ^ Tyrone Taylor      - PH   R   PH T6
    55  ^ Tyrone Taylor      D DH   R   to DH B6
     9  ^ Miguel Amaya       2 C    R   in B9
```

Each team also gets a pitchers-used list — starter plus every reliever with the
inning they entered and who they relieved.

---

## Two ways to use it

### 1. `scorebook.html` — the live page (use this at the ballpark)

A single self-contained file. It talks to `statsapi.mlb.com` and, pregame,
`api.open-meteo.com` directly from the browser (both send
`Access-Control-Allow-Origin: *`), so there is **no server and nothing running at
home**. Open it via a `?gamePk=` link from `index.html` and it fetches current data
for that game.

- **↻ Refresh now** button pinned at the bottom, thumb-reachable.
- **Auto-refresh**, tuned to what's happening: every **30s while the game is
  live** (substitutions land fast), every 60s inside 4 hours of first pitch with
  the card still incomplete, every 60s inside 45 minutes for late scratches, 5
  minutes otherwise, and it stops once the game is Final.
- **Spoiler-safe by default** — no score anywhere, and in-game moves stay hidden
  behind a per-game "Show moves" button.
- **Refreshes on focus** — coming back to the tab re-pulls if data is stale
  (20s during the game, 60s otherwise).
- The status line calls out **new moves since your last pull** ("· 2 new moves")
  — but only for a game you've already revealed.
- **Caches to `localStorage`** — flaky ballpark wifi shows the last good pull
  with an "Offline" marker instead of an error.
- **Header recolors to the home team.**
- Prints cleanly if you'd rather carry paper.

**Try it locally:**

```bash
python3 -m http.server 8777 --directory ~/Scorebook
```

Then open <http://localhost:8777/index.html> and pick a game.

#### Getting it on your phone

The files are fully static, so any static host works. GitHub Pages is the usual
5-minute path:

```bash
cd ~/Scorebook && git init && git add index.html scorebook.html && git commit -m "Eephus halfliner scorebook"
```

Create an empty repo on github.com, then:

```bash
git remote add origin https://github.com/YOUR-USERNAME/scorebook.git && git branch -M main && git push -u origin main
```

In the repo: **Settings → Pages → Source: `main` / root → Save**. About a minute
later it's live at `https://YOUR-USERNAME.github.io/scorebook/`.

Alternatives that need no git: drag the files onto [Netlify Drop](https://app.netlify.com/drop),
or `npx wrangler pages deploy .` for Cloudflare Pages.

**On the phone:** open the URL in Safari → Share → **Add to Home Screen**. It gets
an icon and opens full-screen like an app.

### 2. `scorebook.py` — the CLI

Standard library only, Python 3.9+ (verified).

```bash
./scorebook.py                    # lists today's games, prompts for a pick
```

```bash
./scorebook.py --team CHC         # today's (or next) Cubs game
./scorebook.py --team-id 112      # same, by numeric team id
./scorebook.py --game-pk 776496   # a specific game
```

```bash
./scorebook.py --date 2026-08-24
```

**Watch mode** prints the sheet once, then streams each new substitution as it
happens — one line per move — until the game goes final:

```bash
./scorebook.py --watch
```

It polls every 30s during the game and every 60s pregame (`--interval N` to
override). If you only want the pregame header and no in-game tracking, use
`--watch --until-ready`, which stops as soon as lineups and a posted crew are in.

To see relievers, pinch-hitters, and substitutions, add `--show-moves`:

```bash
./scorebook.py --watch --show-moves
```

Other flags: `--html PATH` writes a standalone HTML snapshot, `--json PATH` dumps
the raw structured data, `--quiet` suppresses the printed sheet, `--no-color` for
piping or printing.

Note `--json` always contains the moves array (it's raw data, for your own use);
the printed sheet and the HTML snapshot respect `--show-moves`.

**Artifact snapshot (backup path):** the HTML from `--html` is publishable as a
private Claude Artifact you can open from the Claude app on your phone:

```bash
./scorebook.py --quiet --html ~/Scorebook/snapshot.html
```

Then ask Claude to republish `snapshot.html` to the existing artifact URL. This is
a *snapshot*, not live — an artifact page can't reach external APIs, so the live
page above is the primary path and this is the fallback.

---

## Things worth knowing before you ink

**Lineups and umpires post ~2–3 hours before first pitch.** Before that the API
genuinely has nothing — starting pitchers, records, managers, venue, and first
pitch are available days ahead, but the batting order and crew are not. Both tools
say so explicitly rather than showing blanks.

**Projected umpire crews.** If the crew isn't posted and it isn't a series opener,
the tools rotate the previous game's crew forward: **HP←1B, 1B←2B, 2B←3B, 3B←HP**.
That's MLB's standard rotation and it's reliable within a series, but it's a
projection — badged `PROJECTED` in yellow. Crews change on travel days and for
injuries, so verify before it goes in pen.

**Starters, not current occupants.** The API's flat `battingOrder[]` array tracks
whoever *currently* holds each slot, so once a game is underway it reports
pinch-hitters. Both tools instead read each player's own `battingOrder` field
(`"S00"` = that slot's starter, `"S01"`/`"S02"` = replacements) and take positions
from `allPositions[0]`, the position they started at. The starting nine stays the
starting nine; substitutes show as their own rows underneath.

**How moves get assigned to a team.** Pitching and defensive changes belong to the
*fielding* team (home in the top half, away in the bottom); pinch-hitters and
pinch-runners belong to the *batting* team. Pitching substitutions never carry a
`replacedPlayer` in the API, so "relieves X" is derived by tracking each team's
pitcher of record forward from the starter.

**Position players pitching** show up correctly — they'll appear both in the
lineup and in the pitchers-used list.

**Doubleheaders** pick the first game that isn't Final; the header shows
"Game 1"/"Game 2". `--team`/`--team-id` roll forward to the next game within 10
days if there's none on the requested date, and say so; `--game-pk` and the
picker always name an exact game, so there's no fallback to report.

**Domed and retractable-roof parks** always show "Domed" for domes; retractable
roofs show the pregame forecast (roof state isn't knowable ahead of time) and
MLB's own actual weather once the game is live or final — MLB already reports
"Roof Closed" as the condition string when the roof is shut.

Positions render in scorebook notation — `8 CF`, `6 SS`, `D DH` — so they drop
straight into the position column. `B` is the batter's side (L/R/S); pitchers show
RHP/LHP.

---

Unofficial. Data © MLB Advanced Media, via `statsapi.mlb.com`, plus forecasts from
`api.open-meteo.com`, for personal scorekeeping.
