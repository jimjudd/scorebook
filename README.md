# Cubs Scorebook

Everything needed to fill out a **Numbers Game #22** scorebook — the header before
first pitch, and every substitution once the game is underway. Pulled from MLB's
public Stats API. No key, no account.

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

## During the game

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

A single self-contained file. It talks to `statsapi.mlb.com` directly from the
browser (the API sends `Access-Control-Allow-Origin: *`), so there is **no server
and nothing running at home**. Open it and it fetches current data.

- **↻ Refresh now** button pinned at the bottom, thumb-reachable.
- **Auto-refresh**, tuned to what's happening: every **30s while the game is
  live** (substitutions land fast), every 60s inside 4 hours of first pitch with
  the card still incomplete, every 60s inside 45 minutes for late scratches, 5
  minutes otherwise, and it stops once the game is Final.
- **Refreshes on focus** — coming back to the tab re-pulls if data is stale
  (20s during the game, 60s otherwise).
- The status line calls out **new moves since your last pull** ("· 2 new moves").
- **Live score strip** replaces the first-pitch clock once the game starts.
- **Caches to `localStorage`** — flaky ballpark wifi shows the last good pull
  with an "Offline" marker instead of an error.
- Date picker for any other day; `?date=YYYY-MM-DD` also works.
- Prints cleanly if you'd rather carry paper.

**Try it locally:**

```bash
python3 -m http.server 8777 --directory ~/Scorebook
```

Then open <http://localhost:8777/scorebook.html>.

#### Getting it on your phone

The file is fully static, so any static host works. GitHub Pages is the usual
5-minute path:

```bash
cd ~/Scorebook && git init && git add scorebook.html && git commit -m "Cubs scorebook"
```

Create an empty repo on github.com, then:

```bash
git remote add origin https://github.com/YOUR-USERNAME/scorebook.git && git branch -M main && git push -u origin main
```

In the repo: **Settings → Pages → Source: `main` / root → Save**. About a minute
later it's live at `https://YOUR-USERNAME.github.io/scorebook/scorebook.html`.

Alternatives that need no git: drag the file onto [Netlify Drop](https://app.netlify.com/drop),
or `npx wrangler pages deploy .` for Cloudflare Pages.

**On the phone:** open the URL in Safari → Share → **Add to Home Screen**. It gets
an icon and opens full-screen like an app.

### 2. `scorebook.py` — the CLI

Standard library only, Python 3.9+ (verified).

```bash
./scorebook.py
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

Other flags: `--html PATH` writes a standalone HTML snapshot, `--json PATH` dumps
the raw structured data, `--quiet` suppresses the printed sheet, `--no-color` for
piping or printing.

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
"Game 1"/"Game 2". **No game today?** Both tools roll forward to the next Cubs
game within 10 days and tell you they did.

Positions render in scorebook notation — `8 CF`, `6 SS`, `D DH` — so they drop
straight into the position column. `B` is the batter's side (L/R/S); pitchers show
RHP/LHP.

---

Unofficial. Data © MLB Advanced Media, via `statsapi.mlb.com`, for personal
scorekeeping.
