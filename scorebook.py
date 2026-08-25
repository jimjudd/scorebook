#!/usr/bin/env python3
"""
Cubs Scorebook — Numbers Game #22 prefill, plus live substitution tracking.

Before the game it gives you everything the scorebook header needs: batting
orders with positions and jersey numbers, starting pitchers, managers, team
records, the umpire crew, first pitch time, and the ballpark.

Once the game starts it keeps going: every pitching change, pinch-hitter,
pinch-runner, and defensive substitution, with the inning each one entered.

Pulls from MLB's public Stats API. No key required.

Usage
-----
  ./scorebook.py                          today's Cubs game, printed
  ./scorebook.py --date 2026-08-24        a specific date
  ./scorebook.py --watch                  poll until the game is final
  ./scorebook.py --watch --until-ready    poll only until the card is fillable
  ./scorebook.py --html sheet.html        write a standalone HTML snapshot
  ./scorebook.py --json sheet.json        write the raw structured data
  ./scorebook.py --no-color               plain text (piping, printing)

Standard library only. Python 3.9+.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

API = "https://statsapi.mlb.com"
TEAM_ID = 112  # Chicago Cubs
CHICAGO = ZoneInfo("America/Chicago")
TIMEOUT = 25

# Position code -> (scorebook number, abbreviation)
POS = {
    "1": ("1", "P"),   "2": ("2", "C"),   "3": ("3", "1B"),
    "4": ("4", "2B"),  "5": ("5", "3B"),  "6": ("6", "SS"),
    "7": ("7", "LF"),  "8": ("8", "CF"),  "9": ("9", "RF"),
    "10": ("D", "DH"), "11": ("-", "PH"), "12": ("-", "PR"),
}


# --------------------------------------------------------------------------
# fetch
# --------------------------------------------------------------------------

def get(path):
    req = urllib.request.Request(
        API + path, headers={"User-Agent": "cubs-scorebook/2.0"}
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.load(r)


def _games(sched):
    out = [g for d in sched.get("dates", []) for g in d.get("games", [])]
    out.sort(key=lambda g: g["gameDate"])
    return out


def find_game(date_str):
    """The Cubs game on date_str, else the next one within 10 days."""
    hyd = "hydrate=probablePitcher,team,venue(timezone)"
    games = _games(get("/api/v1/schedule?sportId=1&teamId=%d&date=%s&%s"
                       % (TEAM_ID, date_str, hyd)))
    if games:
        for g in games:  # doubleheader: first game that isn't over
            if g.get("status", {}).get("abstractGameState") != "Final":
                return g, None
        return games[-1], None

    end = (datetime.strptime(date_str, "%Y-%m-%d")
           + timedelta(days=10)).strftime("%Y-%m-%d")
    games = _games(get("/api/v1/schedule?sportId=1&teamId=%d&startDate=%s&endDate=%s&%s"
                       % (TEAM_ID, date_str, end, hyd)))
    if not games:
        raise SystemExit("No Cubs game on %s or in the next 10 days." % date_str)
    return games[0], games[0]["officialDate"]


_mgr_cache = {}


def manager(team_id):
    if team_id in _mgr_cache:
        return _mgr_cache[team_id]
    try:
        roster = get("/api/v1/teams/%d/coaches" % team_id).get("roster", [])
        name = next((c["person"]["fullName"] for c in roster
                     if c.get("jobId") == "MNGR"), None)
    except Exception:
        name = None
    _mgr_cache[team_id] = name
    return name


def map_officials(officials):
    key = {"Home Plate": "HP", "First Base": "1B",
           "Second Base": "2B", "Third Base": "3B"}
    return {key[o["officialType"]]: o["official"]["fullName"]
            for o in officials if o.get("officialType") in key}


def umpires(game, live):
    """Posted crew, or one projected by rotating the previous game of this series.

    MLB rotates the crew one position per game: HP<-1B, 1B<-2B, 2B<-3B, 3B<-HP.
    Crews change between series, so only rotate within the same matchup.
    """
    posted = live.get("liveData", {}).get("boxscore", {}).get("officials", [])
    if posted:
        return {"crew": map_officials(posted), "projected": False, "from": None}

    d = datetime.fromisoformat(game["gameDate"].replace("Z", "+00:00"))
    start = (d - timedelta(days=6)).strftime("%Y-%m-%d")
    end = (d - timedelta(days=1)).strftime("%Y-%m-%d")
    away = game["teams"]["away"]["team"]["id"]
    home = game["teams"]["home"]["team"]["id"]
    try:
        prior = [
            g for g in _games(get("/api/v1/schedule?sportId=1&teamId=%d"
                                  "&startDate=%s&endDate=%s" % (TEAM_ID, start, end)))
            if {g["teams"]["away"]["team"]["id"], g["teams"]["home"]["team"]["id"]}
            == {away, home}
            and g.get("status", {}).get("abstractGameState") == "Final"
        ]
        if not prior:
            return {"crew": None, "projected": False, "from": None}
        last = prior[-1]
        prev = map_officials(
            get("/api/v1/game/%d/boxscore" % last["gamePk"]).get("officials", []))
        if not all(k in prev for k in ("HP", "1B", "2B", "3B")):
            return {"crew": None, "projected": False, "from": None}
        return {
            "crew": {"HP": prev["1B"], "1B": prev["2B"],
                     "2B": prev["3B"], "3B": prev["HP"]},
            "projected": True,
            "from": last["officialDate"],
        }
    except Exception:
        return {"crew": None, "projected": False, "from": None}


# --------------------------------------------------------------------------
# shape the data
# --------------------------------------------------------------------------

def pos_pair(position):
    if not position:
        return ("-", "--")
    code = str(position.get("code", ""))
    return POS.get(code, (code or "?", position.get("abbreviation", "?")))


def player_index(live):
    """One lookup for every player in the game: name, number, hand, side."""
    idx = {}
    for side in ("away", "home"):
        players = live["liveData"]["boxscore"]["teams"][side].get("players", {})
        for p in players.values():
            pid = p.get("person", {}).get("id")
            if pid is None:
                continue
            e = idx.setdefault(pid, {})
            e["num"] = p.get("jerseyNumber") or e.get("num", "")
            e["side"] = side
            e["name"] = e.get("name") or p.get("person", {}).get("fullName")
    for p in live["gameData"].get("players", {}).values():
        e = idx.setdefault(p["id"], {})
        e["name"] = p.get("fullName") or e.get("name")
        e["num"] = e.get("num") or p.get("primaryNumber") or ""
        e["bats"] = (p.get("batSide") or {}).get("code", "")
        e["throws"] = (p.get("pitchHand") or {}).get("code", "")
    return idx


def starting_nine(box):
    """The nine who START.

    Each boxscore player carries battingOrder "S00" if they started the slot and
    "S01"/"S02" if they replaced someone. The flat battingOrder[] array instead
    tracks the slot's *current* occupant, so it reports pinch-hitters once a game
    is underway. A scorebook always wants the starters.
    """
    out = []
    players = box.get("players", {})
    for p in players.values():
        bo = p.get("battingOrder")
        if bo and str(bo).endswith("00"):
            out.append((int(bo) // 100, p.get("person", {}).get("id"), p))
    if out:
        return sorted(out)
    return [(i + 1, pid, players.get("ID%s" % pid, {}))
            for i, pid in enumerate(box.get("battingOrder", []))]


def build_moves(live):
    """Every substitution in the game, in order.

    Team attribution: pitching and defensive changes belong to the FIELDING team
    (home in the top half, away in the bottom); offensive substitutions -- pinch
    hitters and pinch runners -- belong to the BATTING team.
    """
    moves = []
    for play in live.get("liveData", {}).get("plays", {}).get("allPlays", []):
        about = play.get("about", {})
        for e in play.get("playEvents", []):
            if not e.get("isSubstitution"):
                continue
            det = e.get("details") or {}
            et = det.get("eventType")
            is_top = bool(about.get("isTopInning"))
            if et == "offensive_substitution":
                team = "away" if is_top else "home"
            else:
                team = "home" if is_top else "away"
            pos_num, pos_abbr = pos_pair(e.get("position"))
            if et == "pitching_substitution":
                kind = "pitching"
            elif et == "offensive_substitution":
                kind = "pinch_run" if pos_abbr == "PR" else "pinch_hit"
            elif et == "defensive_substitution":
                kind = "defensive"
            else:
                kind = "switch"
            bo = e.get("battingOrder")
            moves.append({
                "inning": about.get("inning"),
                "is_top": is_top,
                "half": "T" if is_top else "B",
                "team": team,
                "kind": kind,
                "pid": (e.get("player") or {}).get("id"),
                "replaced_id": (e.get("replacedPlayer") or {}).get("id"),
                "pos_num": pos_num,
                "pos": pos_abbr,
                "slot": int(bo) // 100 if bo else None,
                "desc": det.get("description", ""),
            })
    return moves


def pitchers_used(side, moves, idx):
    """Pitchers for one team, in order.

    Pitching substitutions never carry a replacedPlayer, so the man each reliever
    came in for is simply the previous pitcher of record.
    """
    used = []
    if side["sp"]:
        used.append({
            "pid": side["sp"]["pid"], "num": side["sp"]["num"],
            "name": side["sp"]["name"], "throws": side["sp"]["throws"],
            "entered": None, "relieved": None,
        })
    for m in moves:
        if m["kind"] != "pitching" or m["team"] != side["which"]:
            continue
        info = idx.get(m["pid"], {})
        used.append({
            "pid": m["pid"],
            "num": info.get("num", ""),
            "name": info.get("name", "-"),
            "throws": info.get("throws", ""),
            "entered": {"inning": m["inning"], "half": m["half"]},
            "relieved": used[-1]["name"] if used else None,
        })
    return used


def build_side(live, which, idx):
    gd = live["gameData"]
    box = live["liveData"]["boxscore"]["teams"][which]
    team = gd["teams"][which]

    batters = []
    for slot, pid, bx in starting_nine(box):
        per = gd["players"].get("ID%s" % pid, {})
        # allPositions[0] is where they started; position mutates on substitution
        pos_src = (bx.get("allPositions") or [None])[0] or bx.get("position")
        pos_num, pos_abbr = pos_pair(pos_src)
        batters.append({
            "slot": slot,
            "pid": pid,
            "num": bx.get("jerseyNumber") or per.get("primaryNumber") or "",
            "name": (per.get("fullName")
                     or bx.get("person", {}).get("fullName") or "-"),
            "pos_num": pos_num, "pos": pos_abbr,
            "bats": (per.get("batSide") or {}).get("code", ""),
        })

    sp = None
    prob = (gd.get("probablePitchers") or {}).get(which)
    if prob:
        per = gd["players"].get("ID%s" % prob["id"], {})
        bx = box.get("players", {}).get("ID%s" % prob["id"], {})
        sp = {
            "pid": prob["id"],
            "num": bx.get("jerseyNumber") or per.get("primaryNumber") or "",
            "name": prob["fullName"],
            "throws": (per.get("pitchHand") or {}).get("code", ""),
        }

    rec = team.get("record", {}) or {}
    return {
        "which": which,
        "id": team["id"],
        "name": team["name"],
        "short": team.get("teamName") or team["name"],
        "abbrev": team.get("abbreviation", ""),
        "record": ("%d-%d" % (rec["wins"], rec["losses"])
                   if rec.get("wins") is not None else None),
        "pct": rec.get("winningPercentage"),
        "batters": batters,
        "sp": sp,
    }


def load(date_str):
    game, fell_back = find_game(date_str)
    live = get("/api/v1.1/game/%d/feed/live" % game["gamePk"])
    gd = live["gameData"]
    idx = player_index(live)
    moves = build_moves(live)
    away = build_side(live, "away", idx)
    home = build_side(live, "home", idx)
    away["pitchers"] = pitchers_used(away, moves, idx)
    home["pitchers"] = pitchers_used(home, moves, idx)
    tz = (gd["venue"].get("timeZone") or {}).get("id") or "America/Chicago"
    away["manager"] = manager(away["id"])
    home["manager"] = manager(home["id"])
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "requested_date": date_str,
        "fell_back_to": fell_back,
        "game_pk": game["gamePk"],
        "date": game["officialDate"],
        "status": gd.get("status", {}).get("detailedState", ""),
        "abstract": gd.get("status", {}).get("abstractGameState", ""),
        "start_tbd": bool(gd.get("status", {}).get("startTimeTBD")),
        "game_datetime": gd["datetime"]["dateTime"],
        "game_number": game.get("gameNumber", 1),
        "doubleheader": game.get("doubleHeader", "N") != "N",
        "venue": gd["venue"]["name"],
        "venue_tz": tz,
        "venue_tz_abbr": (gd["venue"].get("timeZone") or {}).get("tz", ""),
        "umpires": umpires(game, live),
        "moves": moves,
        "index": {str(k): v for k, v in idx.items()},
        "away": away, "home": home,
    }


def is_ready(d):
    """Everything the scorebook header needs is in hand."""
    return bool(d["away"]["batters"] and d["home"]["batters"]
                and d["umpires"]["crew"] and not d["umpires"]["projected"])


def subs_by_slot(d, which):
    by = {}
    for m in d["moves"]:
        if m["team"] == which and m["slot"] and m["kind"] != "pitching":
            by.setdefault(m["slot"], []).append(m)
    return by


def move_line(d, m):
    """One human-readable line for a substitution."""
    idx = d["index"]
    info = idx.get(str(m["pid"]), {})
    name = info.get("name", "-")
    num = info.get("num", "")
    abbrev = d["away"]["abbrev"] if m["team"] == "away" else d["home"]["abbrev"]
    where = "%s%s" % (m["half"], m["inning"])
    if m["kind"] == "pitching":
        rel = next((p["relieved"] for p in d[m["team"]]["pitchers"]
                    if p["pid"] == m["pid"] and p["entered"]), None)
        tag, body = "P", "%s #%s%s" % (name, num, (" relieves %s" % rel) if rel else "")
    elif m["kind"] == "switch":
        tag, body = "SWAP", "%s moves to %s" % (name, m["pos"])
    else:
        out = idx.get(str(m["replaced_id"]), {}).get("name") if m["replaced_id"] else None
        tag = {"pinch_hit": "PH", "pinch_run": "PR", "defensive": "DEF"}[m["kind"]]
        body = "%s #%s%s%s" % (
            name, num,
            (" for %s" % out) if out else "",
            (" (slot %d)" % m["slot"]) if m["slot"] else "")
    return where, abbrev, tag, body


# --------------------------------------------------------------------------
# render: terminal
# --------------------------------------------------------------------------

class C:
    def __init__(self, on):
        self.on = on

    def __call__(self, code, s):
        return "\033[%sm%s\033[0m" % (code, s) if self.on else str(s)

    def b(self, s):    return self("1", s)
    def dim(self, s):  return self("2", s)
    def blue(self, s): return self("1;34", s)
    def yel(self, s):  return self("33", s)
    def grn(self, s):  return self("32", s)
    def red(self, s):  return self("31", s)


def fmt_time(iso, tz):
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ZoneInfo(tz))
    return dt.strftime("%-I:%M %p")


def fmt_date(iso, tz):
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ZoneInfo(tz))
    return dt.strftime("%a, %b %-d, %Y")


W = 68


def rule(ch="-"):
    return ch * W


def render_text(d, color=True, show_moves=False):
    c = C(color and sys.stdout.isatty())
    L = []
    a, h = d["away"], d["home"]

    if d["fell_back_to"] and d["fell_back_to"] != d["requested_date"]:
        L.append(c.yel("! No Cubs game on %s. Showing %s."
                       % (d["requested_date"], d["fell_back_to"])))
        L.append("")

    L.append(c.blue(rule("=")))
    title = "%s  @  %s" % (a["short"], h["short"])
    if d["doubleheader"]:
        title += "   (Game %d)" % d["game_number"]
    L.append(c.blue(c.b(title.center(W))))
    L.append(c.blue(rule("=")))
    L.append("")

    venue_time = fmt_time(d["game_datetime"], d["venue_tz"])
    L.append("  %s %s" % (c.dim("BALLPARK   "), c.b(d["venue"])))
    L.append("  %s %s" % (c.dim("DATE       "),
                          fmt_date(d["game_datetime"], d["venue_tz"])))
    L.append("  %s %s" % (c.dim("FIRST PITCH"),
                          c.b("TBD" if d["start_tbd"]
                              else "%s %s" % (venue_time, d["venue_tz_abbr"]))))
    here = fmt_time(d["game_datetime"], str(CHICAGO))
    if here != venue_time and not d["start_tbd"]:
        L.append("  %s %s" % (c.dim("           "), c.dim(here + " Chicago time")))
    L.append("  %s %s" % (c.dim("STATUS     "), d["status"]))

    L.append("")

    L.append(c.dim(rule()))
    L.append("  %s  %-36s %s  %s" % (c.dim("AWAY"), c.b(a["name"]),
                                     c.b(a["record"] or "--"), c.dim(a["pct"] or "")))
    L.append("        %s %s" % (c.dim("Manager:"), a["manager"] or "--"))
    L.append("  %s  %-36s %s  %s" % (c.dim("HOME"), c.b(h["name"]),
                                     c.b(h["record"] or "--"), c.dim(h["pct"] or "")))
    L.append("        %s %s" % (c.dim("Manager:"), h["manager"] or "--"))
    L.append("")

    u = d["umpires"]
    L.append(c.dim(rule()))
    L.append("  %s%s" % (c.b("UMPIRES"), c.yel("  [PROJECTED]") if u["projected"] else ""))
    if u["crew"]:
        for k in ("HP", "1B", "2B", "3B"):
            L.append("    %-8s %s" % (c.dim(k + ":"), u["crew"].get(k, "--")))
        if u["projected"]:
            L.append("")
            L.append(c.yel("    Not yet posted. Rotated from the %s game" % u["from"]))
            L.append(c.yel("    of this series (HP<-1B, 1B<-2B, 2B<-3B, 3B<-HP)."))
            L.append(c.yel("    Verify before you ink it."))
    else:
        L.append(c.dim("    Not posted yet -- usually appears with the lineups."))
    L.append("")

    for side, label in ((a, "AWAY"), (h, "HOME")):
        L.append(c.dim(rule()))
        L.append("  %s  %s" % (c.b("%s -- %s" % (label, side["name"])),
                               c.dim(side["record"] or "")))
        L.append("")
        pitchers = side.get("pitchers") or []
        if not show_moves:
            pitchers = pitchers[:1]   # relievers reveal how the game is going
        if pitchers:
            for i, p in enumerate(pitchers):
                tag = "SP" if i == 0 else "RP"
                hand = "%sHP" % p["throws"] if p["throws"] else ""
                when = ("entered %s%s" % (p["entered"]["half"], p["entered"]["inning"])
                        if p["entered"] else "starter")
                nm = c.b(p["name"]) if i == 0 else c.grn(p["name"])
                L.append("    %s  %s  %s  %s"
                         % (c.dim(tag), c.b(str(p["num"]).rjust(2)), nm,
                            c.dim("%s %s" % (hand, when))))
        else:
            L.append(c.dim("    SP  not announced"))
        L.append("")

        if side["batters"]:
            by = subs_by_slot(d, side["which"])
            L.append("    %s" % c.dim("#   No  Batter                     Pos    B"))
            for b in side["batters"]:
                L.append("    %d  %s  %-26s %2s %-3s  %s"
                         % (b["slot"], str(b["num"]).rjust(3), b["name"][:26],
                            b["pos_num"], b["pos"], b["bats"]))
                for m in (by.get(b["slot"], []) if show_moves else []):
                    info = d["index"].get(str(m["pid"]), {})
                    verb = {"pinch_hit": "PH", "pinch_run": "PR",
                            "defensive": "in"}.get(m["kind"],
                                                   "to %s" % m["pos"])
                    L.append("       %s  %s"
                             % (str(info.get("num", "")).rjust(3),
                                c.grn("^ %-24s %2s %-3s  %s  %s"
                                      % (info.get("name", "-")[:24], m["pos_num"],
                                         m["pos"], info.get("bats", ""),
                                         "%s %s%s" % (verb, m["half"], m["inning"])))))
        else:
            L.append(c.dim("    Lineup not posted yet "
                           "(typically 2-3 hours before first pitch)."))
        L.append("")

    if d["moves"] and show_moves:
        L.append(c.dim(rule()))
        L.append("  %s  %s" % (c.b("IN-GAME MOVES"), c.dim("(%d)" % len(d["moves"]))))
        L.append("")
        for m in d["moves"]:
            where, abbrev, tag, body = move_line(d, m)
            L.append("    %-4s %-4s %s %s" % (c.dim(where), c.dim(abbrev),
                                              c.grn("%-4s" % tag), body))
        L.append("")

    L.append(c.dim(rule()))
    fetched = datetime.fromisoformat(d["fetched_at"]).astimezone(CHICAGO)
    L.append(c.dim("  Pulled %s | MLB Stats API | gamePk %s"
                   % (fetched.strftime("%-I:%M:%S %p %Z"), d["game_pk"])))
    return "\n".join(L)


# --------------------------------------------------------------------------
# render: standalone HTML snapshot (no JS -- safe to publish anywhere)
# --------------------------------------------------------------------------

def esc(s):
    return (str("" if s is None else s)
            .replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


CSS = """
:root{--bg:#f4f5f7;--panel:#fff;--ink:#14161a;--muted:#5d6470;--line:#d9dce2;
--cubs:#0e3386;--sub:#0f6b4f;--warn-bg:#fdf3d8;--warn-ink:#7a5a05;--warn-line:#e6cf94;
--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
@media(prefers-color-scheme:dark){:root:not([data-theme="light"]){
--bg:#101216;--panel:#191d24;--ink:#eef1f5;--muted:#9aa3b0;--line:#2b313b;
--cubs:#5b8ce8;--sub:#4fbf95;--warn-bg:#332a10;--warn-ink:#e5c76b;--warn-line:#5a4a1c}}
:root[data-theme="dark"]{--bg:#101216;--panel:#191d24;--ink:#eef1f5;--muted:#9aa3b0;
--line:#2b313b;--cubs:#5b8ce8;--sub:#4fbf95;--warn-bg:#332a10;--warn-ink:#e5c76b;
--warn-line:#5a4a1c}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);margin:0;padding:16px 12px 40px;
font:16px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:720px;margin:0 auto}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;
margin-top:12px;overflow:hidden}
.card h2{margin:0;padding:10px 14px;font-size:11.5px;font-weight:800;letter-spacing:.09em;
text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--line)}
.card h2 .rec{color:var(--ink);font-weight:700}
.body{padding:12px 14px}
.hero{text-align:center;padding:16px 14px}
.matchup{font-size:25px;font-weight:800;letter-spacing:-.02em;text-wrap:balance}
.at{color:var(--muted);font-weight:600;font-size:19px;margin:0 6px}
.park{font-size:15px;color:var(--muted);margin-top:5px}
.fp{font-size:34px;font-weight:800;margin-top:10px;font-variant-numeric:tabular-nums}
.fp small{font-size:16px;color:var(--muted);font-weight:700}
.score{display:flex;align-items:center;justify-content:center;gap:18px;margin-top:12px}
.score .t{text-align:center;min-width:74px}
.score .ab{font-size:11.5px;font-weight:800;letter-spacing:.08em;color:var(--muted)}
.score .r{font-size:38px;font-weight:800;font-variant-numeric:tabular-nums;line-height:1}
.score .inn{font-size:13px;color:var(--muted);font-weight:700;min-width:56px}
.tag{display:inline-block;font-size:11px;font-weight:800;letter-spacing:.06em;
text-transform:uppercase;padding:3px 8px;border-radius:99px;border:1px solid var(--line);
color:var(--muted)}
.kv{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.lbl{font-size:10.5px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
color:var(--muted)}
.val{font-size:16px;font-weight:650;margin-top:2px}
.val .sub{font-weight:400;color:var(--muted);font-size:13.5px}
.tscroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:15.5px}
th{font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);
text-align:left;font-weight:800;padding:6px 4px;border-bottom:1px solid var(--line)}
td{padding:8px 4px;border-bottom:1px solid var(--line)}
tr:last-child td{border-bottom:0}
tr.subrow td{padding-top:5px;padding-bottom:7px;border-bottom:0}
tr.subrow + tr.starter td{border-top:1px solid var(--line)}
tr.subrow .nm{font-weight:600;color:var(--sub);font-size:14.5px}
tr.subrow .num{font-size:14.5px;font-weight:700;color:var(--sub)}
.arrow{color:var(--sub);font-weight:800;margin-right:3px}
.when{color:var(--muted);font-weight:600;font-size:12px;font-family:var(--mono);
margin-left:5px;white-space:nowrap}
.ord{width:22px;font-family:var(--mono);font-weight:700;color:var(--muted);text-align:center}
.num{width:38px;font-family:var(--mono);font-weight:800;font-size:17px;text-align:right;
padding-right:8px;font-variant-numeric:tabular-nums}
.pos{width:56px;text-align:center}
.bt{width:26px;text-align:center;font-family:var(--mono);color:var(--muted);font-size:13.5px}
.chip{display:inline-block;font-family:var(--mono);font-weight:800;font-size:13px;
background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:2px 6px;min-width:34px}
tr.subrow .chip{font-size:12px;font-weight:700}
.pit{display:flex;flex-direction:column;gap:7px}
.pit .row{display:flex;align-items:baseline;gap:9px}
.pit .pt{font-family:var(--mono);font-size:10.5px;font-weight:800;color:var(--muted);
width:22px;flex:none}
.pit .n{font-family:var(--mono);font-weight:800;font-size:18px;min-width:30px;text-align:right;
font-variant-numeric:tabular-nums}
.pit .nm{font-weight:700;font-size:16.5px}
.pit .meta{color:var(--muted);font-size:13px;margin-left:auto;font-family:var(--mono);
white-space:nowrap}
.pit .row.relief .n,.pit .row.relief .nm{color:var(--sub)}
.mv{display:flex;gap:10px;padding:9px 0;border-bottom:1px solid var(--line);align-items:baseline}
.mv:last-child{border-bottom:0}
.mv .inn{font-family:var(--mono);font-weight:800;font-size:13px;color:var(--muted);
width:34px;flex:none}
.mv .tm{font-family:var(--mono);font-weight:800;font-size:11px;padding:2px 5px;border-radius:5px;
border:1px solid var(--line);color:var(--muted);flex:none}
.mv .txt{font-size:14.5px;min-width:0}
.mv .kd{font-family:var(--mono);font-size:10.5px;font-weight:800;color:var(--sub);
letter-spacing:.06em;margin-right:5px}
.mv .out{color:var(--muted)}
.note{background:var(--warn-bg);border:1px solid var(--warn-line);color:var(--warn-ink);
border-radius:10px;padding:10px 12px;font-size:13.5px;margin-top:10px}
.empty{color:var(--muted);font-style:italic;padding:12px 2px;font-size:14.5px}
.foot{text-align:center;color:var(--muted);font-size:11.5px;margin-top:18px;line-height:1.6}
@media print{body{background:#fff}.card{break-inside:avoid}}
"""


def render_html(d, show_moves=False):
    a, h = d["away"], d["home"]
    # First pitch always shows -- it never reveals anything about the outcome.
    t = "TBD" if d["start_tbd"] else fmt_time(d["game_datetime"], d["venue_tz"])
    time_block = ('<div class="fp">%s <small>%s</small></div>'
                  % (esc(t), esc(d["venue_tz_abbr"])))

    def side_block(s, label):
        pitchers = s.get("pitchers") or []
        if not show_moves:
            pitchers = pitchers[:1]
        if pitchers:
            rows = []
            for i, p in enumerate(pitchers):
                hand = "%sHP" % p["throws"] if p["throws"] else ""
                when = ("entered %s%s" % (p["entered"]["half"], p["entered"]["inning"])
                        if p["entered"] else "starter")
                meta = ("%s · %s" % (hand, when)) if hand else when
                rows.append('<div class="row%s"><span class="pt">%s</span>'
                            '<span class="n">%s</span><span class="nm">%s</span>'
                            '<span class="meta">%s</span></div>'
                            % (" relief" if i else "", "RP" if i else "SP",
                               esc(p["num"]), esc(p["name"]), esc(meta)))
            pit = '<div class="pit">%s</div>' % "".join(rows)
        else:
            pit = '<div class="empty">Starter not announced.</div>'

        if s["batters"]:
            by = subs_by_slot(d, s["which"])
            rows = []
            for b in s["batters"]:
                rows.append(
                    '<tr class="starter"><td class="ord">%d</td>'
                    '<td class="num">%s</td><td>%s</td>'
                    '<td class="pos"><span class="chip">%s %s</span></td>'
                    '<td class="bt">%s</td></tr>'
                    % (b["slot"], esc(b["num"]), esc(b["name"]),
                       esc(b["pos_num"]), esc(b["pos"]), esc(b["bats"])))
                for m in (by.get(b["slot"], []) if show_moves else []):
                    info = d["index"].get(str(m["pid"]), {})
                    verb = {"pinch_hit": "PH", "pinch_run": "PR",
                            "defensive": "in"}.get(m["kind"], "to %s" % m["pos"])
                    rows.append(
                        '<tr class="subrow"><td class="ord"></td>'
                        '<td class="num">%s</td>'
                        '<td class="nm"><span class="arrow">&#8627;</span>%s'
                        '<span class="when">%s &middot; %s%s</span></td>'
                        '<td class="pos"><span class="chip">%s %s</span></td>'
                        '<td class="bt">%s</td></tr>'
                        % (esc(info.get("num", "")), esc(info.get("name", "-")),
                           esc(verb), esc(m["half"]), m["inning"],
                           esc(m["pos_num"]), esc(m["pos"]), esc(info.get("bats", ""))))
            table = ('<div class="tscroll"><table><thead><tr><th></th>'
                     '<th class="num">#</th><th>Batter</th><th class="pos">Pos</th>'
                     '<th class="bt">B</th></tr></thead><tbody>%s</tbody></table></div>'
                     % "".join(rows))
        else:
            table = ('<div class="empty">Lineup not posted yet '
                     '(typically 2&ndash;3 hours before first pitch).</div>')

        rec = ' <span class="rec">%s</span>' % esc(s["record"]) if s["record"] else ""
        return ('<div class="card"><h2>%s &middot; %s%s</h2><div class="body">'
                '<div class="lbl">Pitchers</div><div style="height:7px"></div>%s'
                '<div style="height:14px"></div>%s</div></div>'
                % (esc(label), esc(s["name"]), rec, pit, table))

    u = d["umpires"]
    if u["crew"]:
        cells = "".join('<div class="cell"><div class="lbl">%s</div>'
                        '<div class="val">%s</div></div>'
                        % (k, esc(u["crew"].get(k, "&mdash;")))
                        for k in ("HP", "1B", "2B", "3B"))
        note = ("" if not u["projected"] else
                '<div class="note"><b>Projected crew.</b> Not yet posted &mdash; rotated '
                'forward from the %s game of this series (HP&larr;1B, 1B&larr;2B, '
                '2B&larr;3B, 3B&larr;HP). Verify before ink.</div>' % esc(u["from"]))
        umps = '<div class="kv">%s</div>%s' % (cells, note)
    else:
        umps = ('<div class="empty">Umpires not posted yet &mdash; '
                'they usually appear alongside the lineups.</div>')

    if d["moves"] and show_moves:
        rows = []
        for m in d["moves"]:
            where_s, abbrev, tag, body = move_line(d, m)
            rows.append('<div class="mv"><span class="inn">%s</span>'
                        '<span class="tm">%s</span><span class="txt">'
                        '<span class="kd">%s</span>%s</span></div>'
                        % (esc(where_s), esc(abbrev), esc(tag), esc(body)))
        moves_card = ('<div class="card"><h2>In-Game Moves '
                      '<span class="tag">%d</span></h2><div class="body">%s</div></div>'
                      % (len(d["moves"]), "".join(rows)))
    else:
        moves_card = ""

    dh = ' <span class="tag">Game %d</span>' % d["game_number"] if d["doubleheader"] else ""
    fetched = datetime.fromisoformat(d["fetched_at"]).astimezone(CHICAGO)

    return """<meta charset="utf-8">
<title>Cubs Scorebook Prefill</title>
<style>%s</style>
<div class="wrap">
<div class="card hero">
  <div class="matchup">%s<span class="at">@</span>%s</div>
  <div class="park">%s</div>
  <div class="park">%s &middot; <span class="tag">%s</span>%s</div>
  %s
</div>

<div class="card"><h2>Teams</h2><div class="body"><div class="kv">
  <div class="cell"><div class="lbl">Away Record</div><div class="val">%s
    <span class="sub">%s</span></div></div>
  <div class="cell"><div class="lbl">Home Record</div><div class="val">%s
    <span class="sub">%s</span></div></div>
  <div class="cell"><div class="lbl">Away Manager</div><div class="val">%s</div></div>
  <div class="cell"><div class="lbl">Home Manager</div><div class="val">%s</div></div>
</div></div></div>

<div class="card"><h2>Umpires</h2><div class="body">%s</div></div>
%s
%s
%s

<div class="foot">Snapshot pulled %s &middot; MLB Stats API &middot; gamePk %s<br>
Lineups &amp; umpires post ~2&ndash;3 hrs before first pitch &mdash; re-run to refresh.</div>
</div>""" % (
        CSS,
        esc(a["short"]), esc(h["short"]), esc(d["venue"]),
        esc(fmt_date(d["game_datetime"], d["venue_tz"])), esc(d["status"]), dh,
        time_block,
        esc(a["record"] or "&mdash;"), esc(a["pct"] or ""),
        esc(h["record"] or "&mdash;"), esc(h["pct"] or ""),
        esc(a["manager"] or "&mdash;"), esc(h["manager"] or "&mdash;"),
        umps, side_block(a, "Away"), side_block(h, "Home"), moves_card,
        esc(fetched.strftime("%b %-d, %Y at %-I:%M %p %Z")), d["game_pk"])


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Numbers Game #22 scorebook data for Cubs games.")
    ap.add_argument("--date", help="YYYY-MM-DD (default: today, Chicago time)")
    ap.add_argument("--html", metavar="PATH", help="write a standalone HTML snapshot")
    ap.add_argument("--json", metavar="PATH", help="write the raw structured data")
    ap.add_argument("--watch", action="store_true",
                    help="keep polling (until the game is final)")
    ap.add_argument("--until-ready", action="store_true",
                    help="with --watch, stop once lineups and umpires are posted")
    ap.add_argument("--interval", type=int, default=0,
                    help="seconds between polls (default: 60 pregame, 30 in-game)")
    ap.add_argument("--show-moves", action="store_true",
                    help="reveal in-game moves (relievers, pinch-hitters, subs). "
                         "Hidden by default so a recorded game isn't spoiled.")
    ap.add_argument("--quiet", action="store_true", help="suppress the printed sheet")
    ap.add_argument("--no-color", action="store_true", help="plain text output")
    args = ap.parse_args()

    date_str = args.date or datetime.now(CHICAGO).strftime("%Y-%m-%d")
    c = C(not args.no_color and sys.stderr.isatty())
    seen = None  # number of moves already printed, once we're in watch mode

    while True:
        try:
            d = load(date_str)
        except urllib.error.URLError as e:
            print("Network error: %s" % e.reason, file=sys.stderr)
            if not args.watch:
                return 1
            time.sleep(args.interval or 60)
            continue

        if seen is None:
            if not args.quiet:
                print(render_text(d, color=not args.no_color,
                                  show_moves=args.show_moves))
            if args.watch and not args.show_moves and d["moves"]:
                print(c.dim("  (in-game moves hidden -- pass --show-moves to see them)"),
                      file=sys.stderr)
            seen = len(d["moves"])
        else:
            # in watch mode, only announce what's new -- and only if asked
            new = d["moves"][seen:] if args.show_moves else []
            for m in new:
                where, abbrev, tag, body = move_line(d, m)
                print("  %s %-4s %-4s %s" % (c.grn("+"), where, abbrev, body),
                      file=sys.stderr)
            seen = len(d["moves"])

        if args.html:
            with open(args.html, "w", encoding="utf-8") as f:
                f.write(render_html(d, show_moves=args.show_moves))
            if not args.watch:
                print("\nHTML snapshot -> %s" % args.html, file=sys.stderr)
        if args.json:
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump(d, f, indent=2)
            if not args.watch:
                print("JSON -> %s" % args.json, file=sys.stderr)

        if not args.watch:
            return 0
        if d["abstract"] == "Final":
            print(c.dim("\nGame is final. Done watching."), file=sys.stderr)
            return 0
        if args.until_ready and is_ready(d):
            print(c.dim("\nCard is ready (lineups + posted umpires)."), file=sys.stderr)
            return 0

        interval = args.interval or (30 if d["abstract"] == "Live" else 60)
        time.sleep(interval)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
