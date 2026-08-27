# Player Stats Reveal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Testing note:** This project has no JS test framework (two dependency-free static files, no build step). Jim confirmed skipping automated tests for this plan, same as the prior eephus-halfliner-scorebook plan. Steps below substitute **manual verification** — `node --check` against the extracted `<script>` body for syntax, and a Playwright walkthrough against a real game at the end — for the write-test/run-red/implement/run-green cycle used elsewhere.

**Goal:** Add a second, independent reveal gate to `scorebook.html` that shows real box-score stats (IP/H/R/ER/BB/K/BF/TP for pitchers; AB/R/H/BB/LOB/RBI/TB for batters), hidden by default, sourced from data already being fetched.

**Architecture:** The live feed's boxscore already carries a `stats.batting`/`stats.pitching` object per player. `buildSide()` and `pitchersUsed()` attach a mapped `stats` object to each batter/pitcher entry at data-assembly time — no new network calls. A new localStorage key (`eephus-scorebook-stats-<gamePk>`), independent of the existing moves-reveal key, gates rendering of seven extra table columns (batters) and a wrapped stat-chip line (pitchers), following the same gate/button/click-handler pattern already used for in-game moves.

**Tech Stack:** Vanilla ES5-style JS (matches existing file), no build step, no new dependencies.

---

## File Structure

| File | Responsibility |
|---|---|
| `scorebook.html` | **Modified only.** All changes live in the existing `<script>` block: data-layer additions (`playerIndex`, `buildSide`, `pitchersUsed`), new reveal-state helpers, render-layer additions (`lineupTable`, `pitcherList`, `sideCard`, `render`), and the click handler. Plus a handful of new CSS rules in the existing `<style>` block. |

`scorebook.py` is explicitly out of scope (see spec's "Out of scope" section) — no changes.

---

## Task 1: Independent stats-reveal state helpers

**Files:**
- Modify: `scorebook.html:619-624` (right after the existing `setRevealed` function)

- [ ] **Step 1: Add the parallel stats-reveal key/getter/setter**

Current code at `scorebook.html:615-624`:

```js
function revealKey(pk){ return "eephus-scorebook-reveal-" + pk; }
function isRevealed(pk){
  try{ return localStorage.getItem(revealKey(pk)) === "1"; }catch(e){ return false; }
}
function setRevealed(pk, on){
  try{
    if(on) localStorage.setItem(revealKey(pk), "1");
    else   localStorage.removeItem(revealKey(pk));
  }catch(e){}
}
```

Insert immediately after it:

```js

/* Stats reveal is a second, independent spoiler gate: a batter's line or a
   pitcher's box score tells you how the game is going just as much as a
   substitution does. Keyed separately so revealing one never reveals the
   other. */
function statsKey(pk){ return "eephus-scorebook-stats-" + pk; }
function isStatsRevealed(pk){
  try{ return localStorage.getItem(statsKey(pk)) === "1"; }catch(e){ return false; }
}
function setStatsRevealed(pk, on){
  try{
    if(on) localStorage.setItem(statsKey(pk), "1");
    else   localStorage.removeItem(statsKey(pk));
  }catch(e){}
}
```

- [ ] **Step 2: Verify syntax**

```bash
python3 -c "
import re
html = open('scorebook.html').read()
js = re.search(r'<script>(.*)</script>', html, re.S).group(1)
open('/tmp/sb.js','w').write(js)
"
node --check /tmp/sb.js
```
Expected: no output, exit code 0.

- [ ] **Step 3: Commit**

```bash
git add scorebook.html
git commit -m "feat: add independent stats-reveal state helpers"
```

---

## Task 2: Carry batting stats in `playerIndex()`

Sub rows (pinch-hitters/pinch-runners) are rendered from `idx`, not from `side.batters`, so `idx` needs each player's batting line too.

**Files:**
- Modify: `scorebook.html:392-415`

- [ ] **Step 1: Attach a mapped `stats` object per player**

Current code:

```js
function playerIndex(live){
  var idx = {};
  ["away","home"].forEach(function(side){
    var ps = (live.liveData.boxscore.teams[side]||{}).players || {};
    Object.keys(ps).forEach(function(k){
      var p = ps[k], id = (p.person||{}).id;
      if(id==null) return;
      idx[id] = idx[id] || {};
      idx[id].num  = p.jerseyNumber || idx[id].num;
      idx[id].side = side;
      idx[id].name = idx[id].name || (p.person||{}).fullName;
    });
  });
  var gp = live.gameData.players || {};
  Object.keys(gp).forEach(function(k){
    var p = gp[k];
    idx[p.id] = idx[p.id] || {};
    idx[p.id].name   = p.fullName || idx[p.id].name;
    idx[p.id].num    = idx[p.id].num || p.primaryNumber || "";
    idx[p.id].bats   = (p.batSide||{}).code || "";
    idx[p.id].throws = (p.pitchHand||{}).code || "";
  });
  return idx;
}
```

Replace with:

```js
function playerIndex(live){
  var idx = {};
  ["away","home"].forEach(function(side){
    var ps = (live.liveData.boxscore.teams[side]||{}).players || {};
    Object.keys(ps).forEach(function(k){
      var p = ps[k], id = (p.person||{}).id;
      if(id==null) return;
      idx[id] = idx[id] || {};
      idx[id].num  = p.jerseyNumber || idx[id].num;
      idx[id].side = side;
      idx[id].name = idx[id].name || (p.person||{}).fullName;
      var bs = (p.stats||{}).batting;
      if(bs) idx[id].stats = { ab: bs.atBats, r: bs.runs, h: bs.hits, bb: bs.baseOnBalls,
                                lob: bs.leftOnBase, rbi: bs.rbi, tb: bs.totalBases };
    });
  });
  var gp = live.gameData.players || {};
  Object.keys(gp).forEach(function(k){
    var p = gp[k];
    idx[p.id] = idx[p.id] || {};
    idx[p.id].name   = p.fullName || idx[p.id].name;
    idx[p.id].num    = idx[p.id].num || p.primaryNumber || "";
    idx[p.id].bats   = (p.batSide||{}).code || "";
    idx[p.id].throws = (p.pitchHand||{}).code || "";
  });
  return idx;
}
```

- [ ] **Step 2: Verify syntax** (same command as Task 1 Step 2)

- [ ] **Step 3: Commit**

```bash
git add scorebook.html
git commit -m "feat: carry batting stats in playerIndex for sub rows"
```

---

## Task 3: Attach batting stats to starters in `buildSide()`

**Files:**
- Modify: `scorebook.html:501-514`

- [ ] **Step 1: Map `stats.batting` onto each starting batter**

Current code:

```js
  var batters = startingNine(box).map(function(st){
    var bx  = st.bx;
    var per = gd.players["ID"+st.pid] || {};
    // allPositions[0] is where they STARTED; position mutates on substitution.
    var pp  = posPair((bx.allPositions && bx.allPositions[0]) || bx.position);
    return {
      slot: st.slot,
      pid: st.pid,
      num:  bx.jerseyNumber || per.primaryNumber || "",
      name: (per.fullName || (bx.person&&bx.person.fullName) || "—"),
      posNum: pp[0], posAbbr: pp[1],
      bats: ((per.batSide||{}).code) || ""
    };
  });
```

Replace with:

```js
  var batters = startingNine(box).map(function(st){
    var bx  = st.bx;
    var per = gd.players["ID"+st.pid] || {};
    // allPositions[0] is where they STARTED; position mutates on substitution.
    var pp  = posPair((bx.allPositions && bx.allPositions[0]) || bx.position);
    var bs  = (bx.stats||{}).batting || {};
    return {
      slot: st.slot,
      pid: st.pid,
      num:  bx.jerseyNumber || per.primaryNumber || "",
      name: (per.fullName || (bx.person&&bx.person.fullName) || "—"),
      posNum: pp[0], posAbbr: pp[1],
      bats: ((per.batSide||{}).code) || "",
      stats: { ab: bs.atBats, r: bs.runs, h: bs.hits, bb: bs.baseOnBalls,
               lob: bs.leftOnBase, rbi: bs.rbi, tb: bs.totalBases }
    };
  });
```

- [ ] **Step 2: Verify syntax** (same command as Task 1 Step 2)

- [ ] **Step 3: Commit**

```bash
git add scorebook.html
git commit -m "feat: attach batting stats to starters in buildSide"
```

---

## Task 4: Attach pitching stats in `pitchersUsed()`

`pitchersUsed()` currently only receives `(side, moves, idx)` — it needs the team's `box` to look up each pitcher's `stats.pitching`.

**Files:**
- Modify: `scorebook.html:477-494` (`pitchersUsed`)
- Modify: `scorebook.html:552-553` (its two call sites in `loadAll`)

- [ ] **Step 1: Add a `box` parameter and a per-pitcher stats lookup**

Current code:

```js
function pitchersUsed(side, moves, idx){
  var list = [];
  if(side.sp) list.push({ pid: side.sp.pid, num: side.sp.num, name: side.sp.name,
                          throws: side.sp.throws, entered: null });
  moves.filter(function(m){ return m.kind === "pitching" && m.team === side.which; })
       .forEach(function(m){
    var info = idx[m.pid] || {};
    list.push({
      pid: m.pid,
      num: info.num || "",
      name: info.name || "—",
      throws: info.throws || "",
      entered: { inning: m.inning, half: m.half },
      relieved: list.length ? list[list.length-1].name : null
    });
  });
  return list;
}
```

Replace with:

```js
function pitchersUsed(side, moves, idx, box){
  function pStats(pid){
    var p = (box.players||{})["ID"+pid] || {};
    var s = (p.stats||{}).pitching || {};
    return { ip: s.inningsPitched, h: s.hits, r: s.runs, er: s.earnedRuns,
              bb: s.baseOnBalls, k: s.strikeOuts, bf: s.battersFaced, tp: s.numberOfPitches };
  }
  var list = [];
  if(side.sp) list.push({ pid: side.sp.pid, num: side.sp.num, name: side.sp.name,
                          throws: side.sp.throws, entered: null, stats: pStats(side.sp.pid) });
  moves.filter(function(m){ return m.kind === "pitching" && m.team === side.which; })
       .forEach(function(m){
    var info = idx[m.pid] || {};
    list.push({
      pid: m.pid,
      num: info.num || "",
      name: info.name || "—",
      throws: info.throws || "",
      entered: { inning: m.inning, half: m.half },
      relieved: list.length ? list[list.length-1].name : null,
      stats: pStats(m.pid)
    });
  });
  return list;
}
```

- [ ] **Step 2: Pass `box` at both call sites**

Current code (`scorebook.html:552-553`):

```js
      away.pitchers = pitchersUsed(away, moves, idx);
      home.pitchers = pitchersUsed(home, moves, idx);
```

Replace with:

```js
      away.pitchers = pitchersUsed(away, moves, idx, live.liveData.boxscore.teams.away);
      home.pitchers = pitchersUsed(home, moves, idx, live.liveData.boxscore.teams.home);
```

- [ ] **Step 3: Verify syntax** (same command as Task 1 Step 2)

- [ ] **Step 4: Commit**

```bash
git add scorebook.html
git commit -m "feat: attach pitching stats in pitchersUsed"
```

---

## Task 5: Stat formatting helpers

**Files:**
- Modify: `scorebook.html:652-653` (insert right after `subRow`'s closing brace, before `lineupTable`)

- [ ] **Step 1: Add `statCells()` (batters) and `pitcherStatline()` (pitchers)**

Insert between the end of `subRow()` (line 652: `}`) and the start of `lineupTable()` (line 654):

```js

/* Seven right-aligned cells for a batter's line. No plate appearance yet
   (ab falsy) reads as a row of dashes, not a row of zeroes. */
function statCells(s){
  s = s || {};
  var vals = [s.ab, s.r, s.h, s.bb, s.lob, s.rbi, s.tb];
  if(!s.ab) return vals.map(function(){ return '<td class="c-stat">—</td>'; }).join("");
  return vals.map(function(v){ return '<td class="c-stat">'+esc(v==null?0:v)+'</td>'; }).join("");
}

/* Wrapped stat-chip line for a pitcher. No batters faced yet reads as a
   single dash rather than a line of zeroes. */
function pitcherStatline(s){
  s = s || {};
  if(!s.bf) return '<span class="statline">—</span>';
  var ip = s.ip == null ? "0.0" : s.ip;
  return '<span class="statline">IP '+esc(ip)+' · H '+esc(s.h||0)+' · R '+esc(s.r||0)+
    ' · ER '+esc(s.er||0)+' · BB '+esc(s.bb||0)+' · K '+esc(s.k||0)+
    ' · BF '+esc(s.bf||0)+' · TP '+esc(s.tp||0)+'</span>';
}
```

- [ ] **Step 2: Verify syntax** (same command as Task 1 Step 2)

- [ ] **Step 3: Commit**

```bash
git add scorebook.html
git commit -m "feat: add statCells/pitcherStatline formatting helpers"
```

---

## Task 6: Extend `lineupTable()` with the seven stat columns

**Files:**
- Modify: `scorebook.html:637-675` (`subRow` and `lineupTable`)

- [ ] **Step 1: Thread `statsReveal` through `subRow()`**

Current code:

```js
function subRow(m, idx){
  var info = idx[m.pid] || {};
  var verb = m.kind === "pinch_hit" ? "PH"
           : m.kind === "pinch_run" ? "PR"
           : m.kind === "switch"    ? "to " + m.posAbbr
           :                          "in";
  var when = m.half + m.inning;
  return '<tr class="subrow">'+
    '<td class="c-ord"></td>'+
    '<td class="c-num">'+esc(info.num||"")+'</td>'+
    '<td class="c-name"><span class="arrow">↳</span>'+esc(info.name||"—")+
      '<span class="when">'+esc(verb)+' · '+esc(when)+'</span></td>'+
    '<td class="c-pos"><span class="poschip">'+esc(m.posNum)+' '+esc(m.posAbbr)+'</span></td>'+
    '<td class="c-bt">'+esc(info.bats||"")+'</td>'+
  '</tr>';
}
```

Replace with:

```js
function subRow(m, idx, statsReveal){
  var info = idx[m.pid] || {};
  var verb = m.kind === "pinch_hit" ? "PH"
           : m.kind === "pinch_run" ? "PR"
           : m.kind === "switch"    ? "to " + m.posAbbr
           :                          "in";
  var when = m.half + m.inning;
  return '<tr class="subrow">'+
    '<td class="c-ord"></td>'+
    '<td class="c-num">'+esc(info.num||"")+'</td>'+
    '<td class="c-name"><span class="arrow">↳</span>'+esc(info.name||"—")+
      '<span class="when">'+esc(verb)+' · '+esc(when)+'</span></td>'+
    '<td class="c-pos"><span class="poschip">'+esc(m.posNum)+' '+esc(m.posAbbr)+'</span></td>'+
    '<td class="c-bt">'+esc(info.bats||"")+'</td>'+
    (statsReveal ? statCells(info.stats) : '')+
  '</tr>';
}
```

- [ ] **Step 2: Thread `statsReveal` through `lineupTable()` and add the header/body columns**

Current code:

```js
function lineupTable(side, d, reveal){
  if(!side.batters.length){
    return '<div class="empty">Lineup not posted yet. Usually goes up 2–3 hours '+
           'before first pitch — hit Refresh.</div>';
  }
  var by = subsBySlot(d, side.which);
  var rows = side.batters.map(function(b){
    var r = '<tr class="starter">'+
      '<td class="c-ord">'+b.slot+'</td>'+
      '<td class="c-num">'+esc(b.num)+'</td>'+
      '<td class="c-name">'+esc(b.name)+'</td>'+
      '<td class="c-pos"><span class="poschip">'+esc(b.posNum)+' '+esc(b.posAbbr)+'</span></td>'+
      '<td class="c-bt">'+esc(b.bats)+'</td>'+
    '</tr>';
    if(reveal) (by[b.slot]||[]).forEach(function(m){ r += subRow(m, d.idx); });
    return r;
  }).join("");
  return '<div class="tscroll"><table><thead><tr>'+
    '<th class="c-ord"></th><th class="c-num">#</th><th>Batter</th>'+
    '<th class="c-pos">Pos</th><th class="c-bt">B</th>'+
    '</tr></thead><tbody>'+rows+'</tbody></table></div>';
}
```

Replace with:

```js
function lineupTable(side, d, reveal, statsReveal){
  if(!side.batters.length){
    return '<div class="empty">Lineup not posted yet. Usually goes up 2–3 hours '+
           'before first pitch — hit Refresh.</div>';
  }
  var by = subsBySlot(d, side.which);
  var rows = side.batters.map(function(b){
    var r = '<tr class="starter">'+
      '<td class="c-ord">'+b.slot+'</td>'+
      '<td class="c-num">'+esc(b.num)+'</td>'+
      '<td class="c-name">'+esc(b.name)+'</td>'+
      '<td class="c-pos"><span class="poschip">'+esc(b.posNum)+' '+esc(b.posAbbr)+'</span></td>'+
      '<td class="c-bt">'+esc(b.bats)+'</td>'+
      (statsReveal ? statCells(b.stats) : '')+
    '</tr>';
    if(reveal) (by[b.slot]||[]).forEach(function(m){ r += subRow(m, d.idx, statsReveal); });
    return r;
  }).join("");
  var statHeaders = statsReveal
    ? ['AB','R','H','BB','LOB','RBI','TB'].map(function(h){ return '<th class="c-stat">'+h+'</th>'; }).join("")
    : '';
  return '<div class="tscroll"><table><thead><tr>'+
    '<th class="c-ord"></th><th class="c-num">#</th><th>Batter</th>'+
    '<th class="c-pos">Pos</th><th class="c-bt">B</th>'+statHeaders+
    '</tr></thead><tbody>'+rows+'</tbody></table></div>';
}
```

- [ ] **Step 3: Verify syntax** (same command as Task 1 Step 2)

- [ ] **Step 4: Commit**

```bash
git add scorebook.html
git commit -m "feat: render stat columns in lineupTable when revealed"
```

---

## Task 7: Extend `pitcherList()` with the stat-chip line

**Files:**
- Modify: `scorebook.html:677-697`

- [ ] **Step 1: Thread `statsReveal` through, fix the truncation condition, append the stat line**

Current code:

```js
function pitcherList(side, d, reveal){
  var ps = side.pitchers || [];
  if(!ps.length) return '<div class="empty">Starter not announced.</div>';
  if(!reveal) ps = ps.slice(0, 1);   // relievers reveal how the game is going
  var live = d.abstract === "Live";
  var rows = ps.map(function(p, i){
    var isLast = (i === ps.length - 1);
    var cls = "row" + (i ? " relief" : "") + ((live && isLast && i) ? " cur" : "");
    var meta = p.entered
      ? "entered " + p.entered.half + p.entered.inning
      : "starter";
    return '<div class="'+cls+'">'+
      '<span class="tag">'+(i ? "RP" : "SP")+'</span>'+
      '<span class="n">'+esc(p.num)+'</span>'+
      '<span class="nm">'+esc(p.name)+'</span>'+
      (p.throws ? '<span class="meta">'+esc(p.throws)+'HP · '+esc(meta)+'</span>'
                : '<span class="meta">'+esc(meta)+'</span>')+
    '</div>';
  }).join("");
  return '<div class="pit">'+rows+'</div>';
}
```

Replace with:

```js
function pitcherList(side, d, reveal, statsReveal){
  var ps = side.pitchers || [];
  if(!ps.length) return '<div class="empty">Starter not announced.</div>';
  if(!reveal && !statsReveal) ps = ps.slice(0, 1);   // relievers reveal how the game is going
  var live = d.abstract === "Live";
  var rows = ps.map(function(p, i){
    var isLast = (i === ps.length - 1);
    var cls = "row" + (i ? " relief" : "") + ((live && isLast && i) ? " cur" : "");
    var meta = p.entered
      ? "entered " + p.entered.half + p.entered.inning
      : "starter";
    return '<div class="'+cls+'">'+
      '<span class="tag">'+(i ? "RP" : "SP")+'</span>'+
      '<span class="n">'+esc(p.num)+'</span>'+
      '<span class="nm">'+esc(p.name)+'</span>'+
      (p.throws ? '<span class="meta">'+esc(p.throws)+'HP · '+esc(meta)+'</span>'
                : '<span class="meta">'+esc(meta)+'</span>')+
      (statsReveal ? pitcherStatline(p.stats) : '')+
    '</div>';
  }).join("");
  return '<div class="pit">'+rows+'</div>';
}
```

- [ ] **Step 2: Verify syntax** (same command as Task 1 Step 2)

- [ ] **Step 3: Commit**

```bash
git add scorebook.html
git commit -m "feat: render pitcher stat-chip line when revealed"
```

---

## Task 8: Pass `statsReveal` through `sideCard()`

**Files:**
- Modify: `scorebook.html:699-712`

- [ ] **Step 1: Add the parameter and forward it to both children**

Current code:

```js
function sideCard(side, label, d, reveal){
  return '<div class="card">'+
    '<h2>'+esc(label)+' · '+esc(side.name)+
      (side.record ? ' <span class="rec">'+esc(side.record)+'</span>' : '')+
    '</h2>'+
    '<div class="body">'+
      '<div class="lbl">Pitchers</div>'+
      '<div style="height:7px"></div>'+
      pitcherList(side, d, reveal)+
      '<div style="height:14px"></div>'+
      lineupTable(side, d, reveal)+
    '</div>'+
  '</div>';
}
```

Replace with:

```js
function sideCard(side, label, d, reveal, statsReveal){
  return '<div class="card">'+
    '<h2>'+esc(label)+' · '+esc(side.name)+
      (side.record ? ' <span class="rec">'+esc(side.record)+'</span>' : '')+
    '</h2>'+
    '<div class="body">'+
      '<div class="lbl">Pitchers</div>'+
      '<div style="height:7px"></div>'+
      pitcherList(side, d, reveal, statsReveal)+
      '<div style="height:14px"></div>'+
      lineupTable(side, d, reveal, statsReveal)+
    '</div>'+
  '</div>';
}
```

- [ ] **Step 2: Verify syntax** (same command as Task 1 Step 2)

- [ ] **Step 3: Commit**

```bash
git add scorebook.html
git commit -m "feat: thread statsReveal through sideCard"
```

---

## Task 9: Add the stats gate and wire it up in `render()`

**Files:**
- Modify: `scorebook.html:848-873`

- [ ] **Step 1: Compute `statsReveal`/`hasStats`, build the gate, pass `statsReveal` to `sideCard()`**

Current code:

```js
  var reveal = isRevealed(d.gamePk);
  // Is there anything to reveal? Relievers count -- a bullpen tells a story.
  var hasInGame = d.moves.length > 0
               || (d.away.pitchers||[]).length > 1
               || (d.home.pitchers||[]).length > 1;

  var gate = "";
  if(hasInGame && !reveal){
    gate = '<div class="gate">'+
      '<div class="g-txt"><b>In-game moves hidden.</b> Substitutions and relief '+
      'pitchers give away how the game is going.</div>'+
      '<button data-reveal="1">Show moves</button>'+
    '</div>';
  }else if(reveal){
    gate = '<div class="gate">'+
      '<div class="g-txt">Showing in-game moves for this game.</div>'+
      '<button data-reveal="0">Hide</button>'+
    '</div>';
  }

  $("content").innerHTML =
    hero + conditionsCard(d) + info + umps + gate +
    sideCard(d.away, "Away", d, reveal) +
    sideCard(d.home, "Home", d, reveal) +
    movesCard(d, reveal);
}
```

Replace with:

```js
  var reveal = isRevealed(d.gamePk);
  // Is there anything to reveal? Relievers count -- a bullpen tells a story.
  var hasInGame = d.moves.length > 0
               || (d.away.pitchers||[]).length > 1
               || (d.home.pitchers||[]).length > 1;

  var gate = "";
  if(hasInGame && !reveal){
    gate = '<div class="gate">'+
      '<div class="g-txt"><b>In-game moves hidden.</b> Substitutions and relief '+
      'pitchers give away how the game is going.</div>'+
      '<button data-reveal="1">Show moves</button>'+
    '</div>';
  }else if(reveal){
    gate = '<div class="gate">'+
      '<div class="g-txt">Showing in-game moves for this game.</div>'+
      '<button data-reveal="0">Hide</button>'+
    '</div>';
  }

  var statsReveal = isStatsRevealed(d.gamePk);
  var hasStats = [].concat(d.away.batters, d.home.batters).some(function(b){
                   return b.stats && b.stats.ab > 0;
                 })
              || [].concat(d.away.pitchers||[], d.home.pitchers||[]).some(function(p){
                   return p.stats && p.stats.bf > 0;
                 });

  var statsGate = "";
  if(hasStats && !statsReveal){
    statsGate = '<div class="gate">'+
      '<div class="g-txt"><b>Stats hidden.</b> Box-score numbers reveal how '+
      'players are actually performing.</div>'+
      '<button data-stats-reveal="1">Show stats</button>'+
    '</div>';
  }else if(hasStats && statsReveal){
    statsGate = '<div class="gate">'+
      '<div class="g-txt">Showing stats for this game.</div>'+
      '<button data-stats-reveal="0">Hide</button>'+
    '</div>';
  }

  $("content").innerHTML =
    hero + conditionsCard(d) + info + umps + gate + statsGate +
    sideCard(d.away, "Away", d, reveal, statsReveal) +
    sideCard(d.home, "Home", d, reveal, statsReveal) +
    movesCard(d, reveal);
}
```

- [ ] **Step 2: Verify syntax** (same command as Task 1 Step 2)

- [ ] **Step 3: Commit**

```bash
git add scorebook.html
git commit -m "feat: add stats gate to render()"
```

---

## Task 10: Handle stats-gate clicks

The existing delegated click handler only recognizes `data-reveal`. It needs to also recognize `data-stats-reveal` and call the right setter.

**Files:**
- Modify: `scorebook.html:986-994`

- [ ] **Step 1: Recognize both attributes**

Current code:

```js
$("content").addEventListener("click", function(e){
  var el = e.target;
  while(el && el !== this && !(el.getAttribute && el.getAttribute("data-reveal"))){
    el = el.parentNode;
  }
  if(!el || el === this || !state.data) return;
  setRevealed(state.data.gamePk, el.getAttribute("data-reveal") === "1");
  render(state.data);
});
```

Replace with:

```js
$("content").addEventListener("click", function(e){
  var el = e.target;
  while(el && el !== this && !(el.getAttribute &&
        (el.getAttribute("data-reveal") || el.getAttribute("data-stats-reveal")))){
    el = el.parentNode;
  }
  if(!el || el === this || !state.data) return;
  if(el.getAttribute("data-reveal") != null){
    setRevealed(state.data.gamePk, el.getAttribute("data-reveal") === "1");
  }else{
    setStatsRevealed(state.data.gamePk, el.getAttribute("data-stats-reveal") === "1");
  }
  render(state.data);
});
```

- [ ] **Step 2: Verify syntax** (same command as Task 1 Step 2)

- [ ] **Step 3: Commit**

```bash
git add scorebook.html
git commit -m "feat: handle stats-gate clicks"
```

---

## Task 11: CSS for stat columns and the pitcher stat-chip line

**Files:**
- Modify: `scorebook.html:129-143` (end of the `---------- lineup ----------` block through the end of the `---------- pitchers ----------` block)

- [ ] **Step 1: Add `.c-stat` after the existing `.poschip` rules**

Current code (end of lineup CSS block, `scorebook.html:129-131`):

```css
.poschip{display:inline-block;font-family:var(--mono);font-weight:800;font-size:13px;
  background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:2px 6px;min-width:34px}
tr.subrow .poschip{font-size:12px;font-weight:700}
```

Insert immediately after it (still before the `/* ---------- pitchers ---------- */` comment):

```css
.c-stat{width:34px;text-align:right;font-family:var(--mono);font-size:13.5px;
  font-variant-numeric:tabular-nums;padding-right:6px}
th.c-stat{text-align:right}
```

- [ ] **Step 2: Add `.pit .statline` at the end of the pitchers CSS block**

Current code (`scorebook.html:134-143`):

```css
.pit{display:flex;flex-direction:column;gap:7px}
.pit .row{display:flex;align-items:baseline;gap:9px}
.pit .tag{font-family:var(--mono);font-size:10.5px;font-weight:800;color:var(--muted);
  width:22px;flex:none;letter-spacing:.04em}
.pit .n{font-family:var(--mono);font-weight:800;font-size:18px;font-variant-numeric:tabular-nums;
  min-width:30px;text-align:right}
.pit .nm{font-weight:700;font-size:16.5px}
.pit .meta{color:var(--muted);font-size:13px;margin-left:auto;font-family:var(--mono);white-space:nowrap}
.pit .row.relief .n,.pit .row.relief .nm{color:var(--sub)}
.pit .row.cur .nm::after{content:" ●";color:var(--team-accent);font-size:11px;vertical-align:middle}
```

Replace with:

```css
.pit{display:flex;flex-direction:column;gap:7px}
.pit .row{display:flex;align-items:baseline;gap:9px;flex-wrap:wrap}
.pit .tag{font-family:var(--mono);font-size:10.5px;font-weight:800;color:var(--muted);
  width:22px;flex:none;letter-spacing:.04em}
.pit .n{font-family:var(--mono);font-weight:800;font-size:18px;font-variant-numeric:tabular-nums;
  min-width:30px;text-align:right}
.pit .nm{font-weight:700;font-size:16.5px}
.pit .meta{color:var(--muted);font-size:13px;margin-left:auto;font-family:var(--mono);white-space:nowrap}
.pit .row.relief .n,.pit .row.relief .nm{color:var(--sub)}
.pit .row.cur .nm::after{content:" ●";color:var(--team-accent);font-size:11px;vertical-align:middle}
.pit .statline{flex-basis:100%;font-family:var(--mono);font-size:12px;color:var(--muted);
  margin-top:2px;white-space:normal}
```

- [ ] **Step 3: Commit**

```bash
git add scorebook.html
git commit -m "feat: add CSS for stat columns and pitcher stat-chip line"
```

---

## Task 12: Manual end-to-end verification

**Files:** none (verification only)

- [ ] **Step 1: Find a recently completed game's `gamePk`**

```bash
curl -s --max-time 10 "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=$(date -v-1d +%F 2>/dev/null || date -d yesterday +%F)" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); [print(g['gamePk'], g['teams']['away']['team']['name'], '@', g['teams']['home']['team']['name'], g['status']['abstractGameState']) for day in d['dates'] for g in day['games']]"
```

Pick a `gamePk` whose status is `Final` (guarantees pitchers have relieved and batters have stats).

- [ ] **Step 2: Serve the page locally**

```bash
cd /Volumes/Development/scorebook && python3 -m http.server 8811
```

- [ ] **Step 3: Drive it with Playwright and check every state**

Navigate to `http://localhost:8811/scorebook.html?gamePk=<the gamePk from Step 1>` and verify, via snapshot:

1. **Both gates hidden state (moves + stats) render independently:** two separate gate boxes are visible — "In-game moves hidden..." / "Show moves", and "Stats hidden..." / "Show stats" — and only the starting pitcher shows per side.
2. **Click "Show stats" only:** the moves gate still reads "hidden" (unaffected), the stats gate flips to "Showing stats for this game." / "Hide", every pitcher who appeared is now listed (not just the starter) each with a wrapped `IP · H · R · ER · BB · K · BF · TP` line, and the lineup table gains `AB R H BB LOB RBI TB` columns with real numbers (or `—` for anyone with 0 plate appearances).
3. **Reload the page:** stats stay revealed (localStorage persisted), moves stay hidden — confirming the two keys are independent.
4. **Click "Show moves":** substitution rows appear under their batting slot, each row also shows its stat columns since stats reveal is still on.
5. **Click "Hide" on the stats gate:** stat columns and stat-chip lines disappear; the pitcher list collapses back to just the starter (unless moves reveal is also on, in which case relievers still show without stats).

- [ ] **Step 4: Check the browser console for errors**

Use `browser_console_messages` (level: error) after each click in Step 3. Expected: no errors.

- [ ] **Step 5: Stop the local server**

```bash
# kill the python3 -m http.server process started in Step 2
```

No commit for this task — verification only.
