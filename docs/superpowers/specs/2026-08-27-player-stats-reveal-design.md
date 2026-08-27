# Player Stats Reveal — Design

## Background

`scorebook.html` already hides in-game substitutions and relief pitchers
behind a per-game "Show moves" reveal, since they leak how a game is going.
The underlying live feed (`/api/v1.1/game/{gamePk}/feed/live`) also carries
each player's running box-score line, which this design surfaces the same
way: hidden by default, revealed on request, live-updating once shown.

This is a browser-only feature — `scorebook.py` (the CLI) is unaffected.

## Data

`buildSide()` in `scorebook.html` already reads
`live.liveData.boxscore.teams[which].players[...]` to build `batters[]` and
the pitcher list. Each player entry there carries a `stats.batting` or
`stats.pitching` object. This design attaches a `stats` field to each batter
and pitcher object, mapped from those existing fields:

| Display | Batters (`stats.batting`) | Pitchers (`stats.pitching`) |
|---|---|---|
| AB / IP | `atBats` | `inningsPitched` |
| R | `runs` | `runs` |
| H | `hits` | `hits` |
| BB | `baseOnBalls` | `baseOnBalls` |
| LOB | `leftOnBase` | — |
| TB | `totalBases` | — |
| RBI | `rbi` | — |
| ER | — | `earnedRuns` |
| K | — | `strikeOuts` |
| BF | — | `battersFaced` |
| TP | — | `numberOfPitches` |

No new network calls — this data is already present in the feed the page
fetches today.

## Reveal behavior

- New, independent localStorage key `eephus-scorebook-stats-<gamePk>`
  (parallel to the existing `eephus-scorebook-reveal-<gamePk>` moves key).
  Revealing stats does not reveal moves, and vice versa.
- A second gate box (same visual style as the moves gate) appears once
  there's anything to show: any batter with `atBats > 0` or any pitcher with
  `battersFaced > 0`. Before that, the gate doesn't render at all — nothing
  to reveal pregame.
  - Hidden: *"Stats hidden. Box-score numbers reveal how players are
    actually performing."* + **Show stats** button.
  - Revealed: *"Showing stats for this game."* + **Hide** button.
- Once revealed, stats update on the page's normal refresh cycle — no
  separate polling.
- Revealing stats — independent of whether moves are revealed — expands the
  pitcher list to show every pitcher who has appeared, not just the starter.
  Today `pitcherList()` truncates to the starter unless moves are revealed
  (`if(!reveal) ps = ps.slice(0, 1)`); this becomes
  `if(!reveal && !statsReveal) ps = ps.slice(0, 1)`. Without this, a
  reliever's stats would have no row to appear on.

## Layout

Confirmed via mockup against the page's real CSS.

**Batters** — `lineupTable()` already renders a `<table>`. When stats are
revealed, seven columns append after the existing ones (Slot / # / Batter /
Pos / B): **AB, R, H, BB, LOB, TB, RBI**. A batter with no plate appearance
yet shows `—` in every stat cell instead of `0`.

**Pitchers** — `pitcherList()` is a stacked name/meta list, not a table.
Rather than cram eight columns into that layout, each pitcher gets a second,
wrapped line of compact monospace stat labels below their name/meta line:

```
SP #17  Shohei Ohtani           LHP · starter
        IP 6.0 · H 4 · R 2 · ER 2 · BB 1 · K 8 · BF 24 · TP 94
```

A pitcher with no batters faced yet (e.g. a reliever mid-warmup, if ever
listed) shows `—` for every field on that line.

## Out of scope

- `scorebook.py` / CLI output — this is HTML-only.
- Any change to the existing moves-reveal behavior, key, or gate.
- New API calls — all data comes from the feed already being fetched.
