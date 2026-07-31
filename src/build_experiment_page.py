"""
Publish the removal experiment as its own page.

The corpus documents what is being advertised. This page documents something
nobody appears to have measured: whether reporting a violating ad to the
platform actually causes it to come down.

Published while the result is still unknown, deliberately. Registering the
design and the cohort before the outcome is in is what separates a measurement
from a story told afterwards about whichever number turned up.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "ads.db"
OUT = ROOT / "docs" / "experiment.html"

CSS_LINK = """
*,*::before,*::after{box-sizing:border-box}
:root{--bg:#fbfaf8;--fg:#1a1a18;--muted:#6b6b66;--line:#e3e0d9;--card:#fff;
  --accent:#8c2f22;--accent-soft:#f5ebe8;--ok:#2c6e49;--warn:#8a6d1f;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,monospace}
@media (prefers-color-scheme:dark){:root{--bg:#14140f;--fg:#eceae4;--muted:#9a978e;
  --line:#2e2c26;--card:#1c1b16;--accent:#e0705c;--accent-soft:#2a1a16;
  --ok:#6cbf94;--warn:#d4b25f}}
:root[data-theme=dark]{--bg:#14140f;--fg:#eceae4;--muted:#9a978e;--line:#2e2c26;
  --card:#1c1b16;--accent:#e0705c;--accent-soft:#2a1a16;--ok:#6cbf94;--warn:#d4b25f}
:root[data-theme=light]{--bg:#fbfaf8;--fg:#1a1a18;--muted:#6b6b66;--line:#e3e0d9;
  --card:#fff;--accent:#8c2f22;--accent-soft:#f5ebe8;--ok:#2c6e49;--warn:#8a6d1f}
body{margin:0;background:var(--bg);color:var(--fg);
  font:16px/1.65 ui-serif,Georgia,"Times New Roman",serif}
.wrap{max-width:820px;margin:0 auto;padding:0 24px}
header{border-bottom:1px solid var(--line);padding:60px 0 36px;margin-bottom:36px}
h1{font-size:clamp(28px,5vw,42px);line-height:1.14;margin:0 0 14px;letter-spacing:-.02em}
.sub{font-size:19px;color:var(--muted);margin:0;max-width:62ch}
h2{font-size:24px;margin:48px 0 12px;padding-top:20px;border-top:1px solid var(--line)}
h3{font-size:17px;margin:26px 0 6px}
p{max-width:68ch}
a{color:var(--accent)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
  gap:14px;margin:30px 0}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px}
.stat .n{font-size:30px;font-weight:600;font-family:var(--mono);line-height:1}
.stat .l{font-size:13px;color:var(--muted);margin-top:7px;line-height:1.35}
.note{background:var(--accent-soft);border-left:3px solid var(--accent);
  padding:15px 19px;border-radius:0 8px 8px 0;margin:22px 0}
.note p{margin:0}
table{width:100%;border-collapse:collapse;font-size:14px;
  font-family:system-ui,-apple-system,sans-serif}
.scroll{overflow-x:auto;margin:18px 0}
th{text-align:left;padding:9px 11px;border-bottom:2px solid var(--line);
  font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);
  white-space:nowrap}
td{padding:9px 11px;border-bottom:1px solid var(--line);vertical-align:top}
code{font-family:var(--mono);font-size:.88em;background:var(--accent-soft);
  padding:1px 5px;border-radius:4px}
.mono{font-family:var(--mono);font-size:12px}
.pending{color:var(--warn);font-weight:600}
footer{margin:70px 0 40px;padding-top:22px;border-top:1px solid var(--line);
  color:var(--muted);font-size:14px}
"""


def build() -> str:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    arms = {r["arm"]: r["n"] for r in conn.execute(
        "SELECT arm, COUNT(*) n FROM experiment GROUP BY arm")}
    reported = conn.execute(
        "SELECT COUNT(*) n FROM experiment WHERE reported_at IS NOT NULL"
    ).fetchone()["n"]
    advertisers = conn.execute(
        "SELECT COUNT(DISTINCT advertiser) n FROM experiment").fetchone()["n"]
    pairs = conn.execute(
        "SELECT advertiser, COUNT(*) n, SUM(reported_at IS NOT NULL) filed "
        "FROM experiment GROUP BY advertiser ORDER BY n DESC"
    ).fetchall()
    latest = conn.execute("SELECT MAX(observed_at) m FROM observation").fetchone()["m"]
    obs = conn.execute(
        "SELECT e.arm, o.state, COUNT(*) n FROM observation o "
        "JOIN experiment e ON e.creative_id = o.creative_id "
        "WHERE o.observed_at = ? GROUP BY 1,2", (latest,)
    ).fetchall() if latest else []
    conn.close()

    adv_rows = "\n".join(
        f"<tr><td>{r['advertiser']}</td><td class='mono'>{r['n']}</td>"
        f"<td class='mono'>{r['filed']}</td></tr>" for r in pairs)
    obs_rows = "\n".join(
        f"<tr><td>{r['arm']}</td><td>{r['state']}</td><td class='mono'>{r['n']}</td></tr>"
        for r in obs) or "<tr><td colspan=3>baseline only</td></tr>"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Does reporting a nicotine ad actually get it removed?</title>
<meta name="description" content="A pre-registered experiment measuring whether
reporting violating nicotine advertising to Google produces removals, against a
matched control arm.">
<style>{CSS_LINK}</style>
</head>
<body>
<div class="wrap">

<header>
<h1>Does reporting an ad actually get it removed?</h1>
<p class="sub">Advocacy groups spend real effort filing platform complaints
about nicotine marketing. No published study measures whether that works. This
one does, and it is posted before the answer is known.</p>
</header>

<div class="stats">
  <div class="stat"><div class="n">{arms.get('reported', 0)}</div>
    <div class="l">creatives in the reported arm</div></div>
  <div class="stat"><div class="n">{arms.get('control', 0)}</div>
    <div class="l">matched controls, deliberately not reported</div></div>
  <div class="stat"><div class="n">{reported}</div>
    <div class="l">reports filed to date</div></div>
  <div class="stat"><div class="n">{advertisers}</div>
    <div class="l">advertisers represented</div></div>
</div>

<h2>Why a control arm</h2>
<p>Reported ads alone prove nothing. Campaigns end on their own, so an ad that
disappears two weeks after a complaint may simply have run its course. Without a
comparison you cannot separate a takedown from an expiry, and you will read
whichever number appears as a success.</p>

<p>So every reported creative is paired with a control drawn from the same
advertiser, the same product category, and the closest available impression
volume, which is deliberately never reported. The comparison between arms is
the result. The reported arm alone is an anecdote.</p>

<h2>What counts as an outcome</h2>
<p>Outcomes are read from Google's own published data, not from anything this
project asserts:</p>

<div class="scroll">
<table>
<thead><tr><th>Reading</th><th>Meaning</th></tr></thead>
<tbody>
<tr><td class="mono">running</td><td>still in <code>creative_stats</code>, last-shown date advancing</td></tr>
<tr><td class="mono">stopped</td><td>still listed, last-shown date frozen</td></tr>
<tr><td class="mono">withdrawn</td><td>absent from <code>creative_stats</code></td></tr>
<tr><td class="mono">removed</td><td>present in <code>removed_creative_stats</code>, which carries the
removal reason, the violation category, and whether detection was automated</td></tr>
</tbody>
</table>
</div>

<p>That last row is the one that matters. It is the only reading that
distinguishes a policy takedown from an advertiser ending a campaign, and it
comes from Google rather than from inference.</p>

<h2>Why snus, and only snus</h2>
<p>The cohort is restricted to snus advertisers. That is not arbitrary.</p>

<p>Google's advertising policy enumerates <em>"Cigarettes, cigars, snus,
chewing tobacco, rolling tobacco, pipe tobacco"</em>. Snus is named outright, so
the claim needs no interpretation. Separately, Directive 2003/33/EC art. 3(2)
extends the tobacco advertising prohibition to "information society services",
and Sweden's accession exemption covers placing on the market, not advertising.
The claim is strong on both the policy and the legal limb.</p>

<div class="note">
<p><strong>A category that was removed from the cohort.</strong> The first draft
included advertisers classified as multi-category. Spot-checking their live
creatives showed British American Tobacco Austria was running <em>VELO nicotine
pouch</em> ads — "Teste jetzt die VELO Nicotine Pouches". Google's policy never
uses the word "nicotine" and does not reach tobacco-free pouches, and pouch
advertising is lawful in Austria until February 2028. Reporting those would have
been a losing claim, and losing claims contaminate a measurement. They were
dropped before any report was filed.</p>
</div>

<h2>Cohort</h2>
<div class="scroll">
<table>
<thead><tr><th>Advertiser</th><th>Creatives enrolled</th><th>Reports filed</th></tr></thead>
<tbody>{adv_rows}</tbody>
</table>
</div>

<h2>Observations</h2>
<p>Latest reading: <span class="mono">{latest or 'baseline pending'}</span></p>
<div class="scroll">
<table>
<thead><tr><th>Arm</th><th>State</th><th>Count</th></tr></thead>
<tbody>{obs_rows}</tbody>
</table>
</div>
<p class="pending">Result not yet known. This page updates as observations
accumulate.</p>

<h2>Limits worth stating now</h2>
<p>The sample is small, and it is drawn from one platform in one region, so it
measures Google's EEA behaviour and nothing broader. Filing is paced because the
reporting form throttles after a couple of submissions per session, which means
the reported arm is filed over days rather than at one instant — reporting dates
are recorded per creative so that exposure time can be accounted for.</p>

<p>A null result is a real result here. If reported ads come down at the same
rate as controls, that is worth knowing, and it will be published exactly as
readily as the alternative.</p>

<footer>
<p><a href="./">Back to the corpus</a> ·
<a href="https://github.com/Ahmet-Dedeler/eliminate-cigarettes">Code and data</a></p>
<p>Generated {date.today().isoformat()}.</p>
</footer>

</div>
</body>
</html>
"""


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT}")
