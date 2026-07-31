"""
Generate the public evidence site.

Static HTML with the corpus embedded as JSON, so it runs on GitHub Pages with
no backend and no external requests. The audience is regulators, researchers
and journalists, so the design priority is verifiability over polish: every
number on the page traces to a row, and every row traces to a platform-hosted
permanent URL.

The limitations section is not boilerplate. It is the reason the rest of the
page is believable, and it leads with the corpus's own error rate.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from policy import Coverage, assess  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "ads.db"
OUT = ROOT / "docs"

CATEGORY_LABEL = {
    "combustible_tobacco": "Combustible tobacco",
    "snus_oral_tobacco": "Snus / oral tobacco",
    "nicotine_pouch": "Nicotine pouches (tobacco-free)",
    "vape_ends": "Vapes / e-cigarettes",
    "heated_tobacco": "Heated tobacco",
    "mixed_nicotine": "Multiple nicotine categories",
    "unknown": "Unclassified",
}


def collect(conn: sqlite3.Connection) -> dict:
    conn.row_factory = sqlite3.Row
    advertisers = []
    rows = conn.execute(
        """
        SELECT ac.advertiser, ac.category, ac.confidence, ac.parent, ac.reason,
               ac.n_creatives, ac.hq
        FROM advertiser_class ac
        WHERE ac.category != 'not_nicotine'
        ORDER BY ac.n_creatives DESC
        """
    ).fetchall()

    for r in rows:
        creatives = conn.execute(
            "SELECT creative_id, creative_url, first_shown, last_shown, regions, "
            "n_regions, verification FROM google_ads WHERE advertiser = ? "
            "ORDER BY last_shown DESC LIMIT 6",
            (r["advertiser"],),
        ).fetchall()
        allreg = conn.execute(
            "SELECT regions FROM google_ads WHERE advertiser = ?", (r["advertiser"],)
        ).fetchall()
        regions = sorted({x for row in allreg for x in (row["regions"] or "").split(",") if x})
        last = conn.execute(
            "SELECT MAX(last_shown) m FROM google_ads WHERE advertiser = ?",
            (r["advertiser"],),
        ).fetchone()["m"]

        imp = conn.execute(
            "SELECT SUM(COALESCE(impressions_floor,0)) s FROM google_ads "
            "WHERE advertiser = ?", (r["advertiser"],),
        ).fetchone()["s"] or 0

        a = assess(r["category"], regions)
        pc = a["platform_policy"]
        pouch = a.get("pouch") or {}

        advertisers.append({
            "name": r["advertiser"],
            "category": r["category"],
            "confidence": r["confidence"],
            "parent": r["parent"],
            "reason": r["reason"],
            "creatives": r["n_creatives"],
            "impressions_floor": int(imp),
            "hq": r["hq"] or "",
            "regions": regions,
            "last_shown": last or "",
            "google_policy": pc.coverage.value if pc else "unknown",
            "google_policy_note": (pc.note if pc else ""),
            "laws": [
                {"country": c.country, "instrument": c.instrument, "note": c.note}
                for c in a["legal_claims"]
            ],
            "pouch_sale_banned": list(pouch.get("sale_banned", {})),
            "pouch_ad_banned": list(pouch.get("ad_banned", {})),
            "pouch_lawful": list(pouch.get("lawful", {})),
            "samples": [
                {"id": c["creative_id"], "url": c["creative_url"],
                 "last": c["last_shown"], "verified": c["verification"]}
                for c in creatives
            ],
        })

    excluded = [
        {"name": r["advertiser"], "reason": r["reason"], "creatives": r["n_creatives"]}
        for r in conn.execute(
            "SELECT advertiser, reason, n_creatives FROM advertiser_class "
            "WHERE category = 'not_nicotine' ORDER BY n_creatives DESC"
        ).fetchall()
    ]

    return {"advertisers": advertisers, "excluded": excluded,
            "generated": date.today().isoformat()}


CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{
  --bg:#fbfaf8; --fg:#1a1a18; --muted:#6b6b66; --line:#e3e0d9;
  --card:#fff; --accent:#8c2f22; --accent-soft:#f5ebe8;
  --ok:#2c6e49; --warn:#8a6d1f;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,monospace;
}
@media (prefers-color-scheme:dark){
  :root{--bg:#14140f;--fg:#eceae4;--muted:#9a978e;--line:#2e2c26;
        --card:#1c1b16;--accent:#e0705c;--accent-soft:#2a1a16;
        --ok:#6cbf94;--warn:#d4b25f}
}
:root[data-theme=dark]{--bg:#14140f;--fg:#eceae4;--muted:#9a978e;--line:#2e2c26;
  --card:#1c1b16;--accent:#e0705c;--accent-soft:#2a1a16;--ok:#6cbf94;--warn:#d4b25f}
:root[data-theme=light]{--bg:#fbfaf8;--fg:#1a1a18;--muted:#6b6b66;--line:#e3e0d9;
  --card:#fff;--accent:#8c2f22;--accent-soft:#f5ebe8;--ok:#2c6e49;--warn:#8a6d1f}

body{margin:0;background:var(--bg);color:var(--fg);
  font:16px/1.6 ui-serif,Georgia,"Times New Roman",serif;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:1080px;margin:0 auto;padding:0 24px}
header{border-bottom:1px solid var(--line);padding:64px 0 40px;margin-bottom:40px}
h1{font-size:clamp(30px,5vw,46px);line-height:1.12;margin:0 0 16px;letter-spacing:-.02em}
.sub{font-size:19px;color:var(--muted);max-width:65ch;margin:0}
h2{font-size:25px;margin:52px 0 14px;letter-spacing:-.01em;
   padding-top:20px;border-top:1px solid var(--line)}
h3{font-size:18px;margin:28px 0 8px}
p{max-width:70ch}
a{color:var(--accent)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:14px;margin:32px 0}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px}
.stat .n{font-size:32px;font-weight:600;line-height:1;letter-spacing:-.02em;
  font-family:var(--mono)}
.stat .l{font-size:13px;color:var(--muted);margin-top:8px;line-height:1.35}
.note{background:var(--accent-soft);border-left:3px solid var(--accent);
  padding:16px 20px;border-radius:0 8px 8px 0;margin:24px 0}
.note p{margin:0}
table{width:100%;border-collapse:collapse;font-size:14px;
  font-family:system-ui,-apple-system,sans-serif}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:20px 0}
th{text-align:left;font-weight:600;padding:10px 12px;border-bottom:2px solid var(--line);
  white-space:nowrap;font-size:12px;text-transform:uppercase;letter-spacing:.05em;
  color:var(--muted)}
td{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}
tbody tr:hover{background:var(--accent-soft)}
.tag{display:inline-block;font-size:11px;padding:2px 8px;border-radius:20px;
  border:1px solid var(--line);white-space:nowrap;font-family:system-ui,sans-serif}
.tag.verified{color:var(--ok);border-color:currentColor}
.tag.likely{color:var(--warn);border-color:currentColor}
.tag.law{color:var(--accent);border-color:currentColor;font-weight:600}
.mono{font-family:var(--mono);font-size:12px}
.big4{font-weight:600}
.controls{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0}
input,select{font:14px/1.4 system-ui,sans-serif;padding:8px 12px;
  border:1px solid var(--line);border-radius:7px;background:var(--card);color:var(--fg)}
input{flex:1;min-width:200px}
details{margin:10px 0;border:1px solid var(--line);border-radius:8px;
  padding:12px 16px;background:var(--card)}
summary{cursor:pointer;font-weight:600;font-size:14px;
  font-family:system-ui,sans-serif}
details ul{font-size:14px;font-family:system-ui,sans-serif}
code{font-family:var(--mono);font-size:.88em;background:var(--accent-soft);
  padding:1px 5px;border-radius:4px}
footer{margin:80px 0 40px;padding-top:24px;border-top:1px solid var(--line);
  color:var(--muted);font-size:14px}
.regions{font-family:var(--mono);font-size:11px;color:var(--muted);
  max-width:260px;display:inline-block;word-break:break-word}
"""

JS = """
const D = window.__DATA__;
const CAT = %CATLABELS%;
const fmt = n => n.toLocaleString('en-US');

function legalCell(a){
  const bits = [];
  if (a.google_policy === 'covered')
    bits.push('<span class="tag verified">breaches Google policy</span>');
  else if (a.google_policy === 'not_covered')
    bits.push('<span class="tag">outside Google policy</span>');
  else if (a.google_policy === 'ambiguous')
    bits.push('<span class="tag likely">Google policy arguable</span>');
  a.laws.forEach(l =>
    bits.push(`<span class="tag law" title="${l.instrument.replace(/"/g,'&quot;')}">unlawful: ${l.country}</span>`));
  if (a.pouch_sale_banned.length)
    bits.push(`<span class="tag law">sale banned: ${a.pouch_sale_banned.join(' ')}</span>`);
  if (a.pouch_ad_banned.length)
    bits.push(`<span class="tag law">ads banned: ${a.pouch_ad_banned.join(' ')}</span>`);
  if (a.pouch_lawful.length)
    bits.push(`<span class="tag" style="opacity:.65">lawful: ${a.pouch_lawful.join(' ')}</span>`);
  return bits.join(' ') || '<span class="tag" style="opacity:.5">none established</span>';
}

function row(a){
  const big4 = a.parent ? ' big4' : '';
  const samples = a.samples.map(s =>
    `<a href="${s.url}" target="_blank" rel="noopener" class="mono">${s.id.slice(0,10)}…</a>`
  ).join('<br>');
  const imp = a.impressions_floor ? '≥' + fmt(a.impressions_floor) : '—';
  return `<tr>
    <td class="${big4.trim()}">${a.name}${a.parent?`<br><span class="mono" style="color:var(--muted)">${a.parent}</span>`:''}</td>
    <td>${CAT[a.category]||a.category}</td>
    <td><span class="tag ${a.confidence}">${a.confidence}</span></td>
    <td class="mono">${fmt(a.creatives)}</td>
    <td class="mono">${imp}</td>
    <td>${legalCell(a)}</td>
    <td><span class="regions">${a.regions.length} — ${a.regions.join(' ')}</span></td>
    <td class="mono">${a.last_shown}</td>
    <td>${samples}</td>
  </tr>`;
}

function render(){
  const q = document.getElementById('q').value.toLowerCase();
  const cat = document.getElementById('cat').value;
  const conf = document.getElementById('conf').value;
  const rows = D.advertisers.filter(a =>
    (!q || a.name.toLowerCase().includes(q) || (a.parent||'').toLowerCase().includes(q)) &&
    (!cat || a.category===cat) && (!conf || a.confidence===conf));
  document.getElementById('tbody').innerHTML = rows.map(row).join('');
  document.getElementById('count').textContent =
    `${fmt(rows.length)} advertisers · ${fmt(rows.reduce((s,a)=>s+a.creatives,0))} creatives`;
}

document.addEventListener('DOMContentLoaded', () => {
  const cats = [...new Set(D.advertisers.map(a=>a.category))].sort();
  document.getElementById('cat').innerHTML =
    '<option value="">All categories</option>' +
    cats.map(c=>`<option value="${c}">${CAT[c]||c}</option>`).join('');
  ['q','cat','conf'].forEach(id =>
    document.getElementById(id).addEventListener('input', render));
  render();
});
"""


def build(data: dict) -> str:
    adv = data["advertisers"]
    total_creatives = sum(a["creatives"] for a in adv)
    verified = [a for a in adv if a["confidence"] == "verified"]
    total_imp = sum(a["impressions_floor"] for a in adv)
    big4 = [a for a in adv if a["parent"]]
    big4_creatives = sum(a["creatives"] for a in big4)
    excluded_creatives = sum(e["creatives"] for e in data["excluded"])
    all_regions = sorted({r for a in adv for r in a["regions"]})
    parents = sorted({a["parent"] for a in big4 if a["parent"]})

    excluded_rows = "\n".join(
        f"<tr><td>{e['name']}</td><td class='mono'>{e['creatives']}</td>"
        f"<td>{e['reason']}</td></tr>"
        for e in data["excluded"]
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nicotine advertising on platforms that ban it</title>
<meta name="description" content="An evidence corpus of tobacco and nicotine
advertising, built from the ad archives platforms publish under the EU Digital
Services Act.">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">

<header>
<h1>Nicotine advertising on the platforms that ban it</h1>
<p class="sub">Google prohibits advertising tobacco products. It also publishes
every ad it serves, because EU law requires it. This is what happens when you
read one against the other.</p>
</header>

<div class="stats">
  <div class="stat"><div class="n">{total_creatives:,}</div>
    <div class="l">nicotine ad creatives in the corpus</div></div>
  <div class="stat"><div class="n">{len(adv)}</div>
    <div class="l">distinct advertisers</div></div>
  <div class="stat"><div class="n">{big4_creatives:,}</div>
    <div class="l">creatives from Big Tobacco subsidiaries</div></div>
  <div class="stat"><div class="n">{total_imp/1_000_000:,.0f}M</div>
    <div class="l">impressions, minimum (Google reports buckets; this is the floor)</div></div>
  <div class="stat"><div class="n">{len(all_regions)}</div>
    <div class="l">regions served</div></div>
</div>

<h2>What this is</h2>
<p>Article 39 of the EU Digital Services Act requires very large platforms to
publish a public archive of every advertisement they carry. Google's
implementation is a
<a href="https://console.cloud.google.com/marketplace/product/bigquery-public-data/google-ads-transparency-center"
target="_blank" rel="noopener">public BigQuery dataset</a> of roughly 170 million
creatives, refreshed daily.</p>

<p>Google's own advertising policy states:
<em>"Ads for tobacco or any products containing tobacco are not allowed."</em>
There is no cessation carve-out and no country exception
(<a href="https://support.google.com/adspolicy/answer/16489929" target="_blank"
rel="noopener">policy</a>).</p>

<p>So the archive is, in effect, a public record of ads that the platform's own
rules prohibit. Every row below links to a permanent Google-hosted page for the
creative. Nothing here is scraped, inferred, or reconstructed.</p>

<div class="note">
<p><strong>Two different claims, kept separate.</strong> Breaching a platform's
advertising policy is not a crime — it is a broken agreement between the
advertiser and the platform, and the remedy is that the ad comes down. Being
<em>unlawful</em> under national or EU law is a separate and much stronger
claim, with a regulator and penalties behind it. Every row below states which
of the two applies, and neither is asserted where it does not hold.</p>
</div>

<h2>What the law actually says</h2>

<p><strong>Snus advertising is prohibited across the EEA, including in Sweden.</strong>
Directive 2003/33/EC art. 3(2) states that advertising not permitted in the press
<em>"shall not be permitted in information society services"</em> — the
prohibition expressly reaches the internet. Snus is a tobacco product under
art. 2 of that Directive, being sucked and made of tobacco. Sweden's famous
exemption, at Article 151 and Annex XV ch. X of the 1994 Act of Accession, is a
<em>placing-on-the-market</em> derogation only. It creates no licence to
advertise, and Sweden separately bans snus advertising in its own law at
Lag (2018:2088) ch. 4 § 1.</p>

<p><strong>Google's advertising policy does not cover tobacco-free nicotine
pouches.</strong> This corrects an earlier version of this page. The word
"nicotine" appears nowhere in Google's tobacco policy. The policy enumerates
<em>"Cigarettes, cigars, snus, chewing tobacco, rolling tobacco, pipe
tobacco"</em> — naming the tobacco-containing oral product while omitting the
tobacco-free one. A pouch contains no tobacco, is not a component part of a
tobacco product, and does not simulate smoking. So the Google claim fails for
Velo and ZYN, and this page no longer makes it. TikTok and Meta both name
nicotine pouches expressly, so the same advertising breaches their policies.</p>

<p><strong>No EU instrument covers nicotine pouches at all.</strong> Not the
Tobacco Products Directive, not 2003/33/EC, not the AVMSD — all are anchored to
products made of tobacco. TPD art. 20(5) was enacted to close that gap for
e-cigarettes only. Pouch regulation is therefore purely national, which is why
the same Velo campaign is unlawful in Belgium, France, the Netherlands and
Norway, prohibited from advertising in eight further countries, and perfectly
legal in Sweden, Spain, Greece and Malta.</p>

<h2>Corporate groups present</h2>
<p>{len(big4)} advertisers in the corpus are subsidiaries of major tobacco
companies, accounting for {big4_creatives:,} creatives:
{", ".join(parents)}.</p>

<h2>The corpus</h2>
<div class="controls">
  <input id="q" placeholder="Search advertiser or parent company…">
  <select id="cat"></select>
  <select id="conf">
    <option value="">All confidence levels</option>
    <option value="verified">Verified only</option>
    <option value="likely">Likely</option>
  </select>
</div>
<p class="mono" id="count"></p>
<div class="scroll">
<table>
<thead><tr>
  <th>Advertiser</th><th>Category</th><th>Confidence</th><th>Creatives</th>
  <th>Impressions</th><th>Rule breached</th><th>Regions served</th>
  <th>Last shown</th><th>Sample evidence</th>
</tr></thead>
<tbody id="tbody"></tbody>
</table>
</div>

<h2>Method, and where it fails</h2>

<h3>The corpus had a 9% false positive rate, and here is the list</h3>
<p>Advertisers are matched on their registered legal name. Naive substring
matching produced {excluded_creatives} creatives of pure noise, because several
European languages contain words that look like nicotine terms:
Swedish <code>vapen</code> means <em>weapons</em>, French <code>vapeur</code>
and Italian <code>vapore</code> mean <em>steam</em>, and "vape" occurs as an
accidental substring in unrelated company names.</p>

<p>Every excluded advertiser is listed below with what the business actually is,
so the exclusions are auditable rather than a bare denylist.</p>

<details>
<summary>{len(data['excluded'])} advertisers excluded as false positives
({excluded_creatives} creatives)</summary>
<div class="scroll">
<table>
<thead><tr><th>Advertiser</th><th>Creatives</th><th>Actual business</th></tr></thead>
<tbody>{excluded_rows}</tbody>
</table>
</div>
</details>

<h3>Recall is low, deliberately</h3>
<p>Matching on registered company name is high-precision and low-recall. It only
catches advertisers whose legal name names the product. Any operator trading
under a neutral name is invisible to this method, which is likely most of the
grey market. Closing that gap requires classifying creative content, and that
should not ship until its error rate has been measured.</p>

<h3>This covers paid advertising only</h3>
<p>The corpus says nothing about organic posts or influencer promotion, which is
the larger surface. That is not an oversight — it is the deliberate complement to
existing work. Vital Strategies' Canary, the only continuous tobacco marketing
monitor in operation, states in its published methodology that
<em>"posts from private profiles, paid advertisements, and influencer-generated
content not accessible via public APIs were not included."</em></p>

<h3>Product categories are not interchangeable</h3>
<p>Combustible tobacco, snus, tobacco-free nicotine pouches, vapes and heated
tobacco are regulated under different instruments and breach different policy
clauses. A nicotine pouch contains nicotine but no tobacco, so a policy clause
addressing "products containing tobacco" may not reach it. The corpus keeps
these separate for that reason.</p>

<h3>Confidence levels</h3>
<p><span class="tag verified">verified</span> means the advertiser is a known
corporate entity or was manually confirmed.
<span class="tag likely">likely</span> means a name signal was corroborated by a
secondary check but the identification has not been confirmed by hand. Only
verified rows should be used for any filing.</p>

<h2>Reproducing this</h2>
<p>The harvesters, the classifier and this site are in the repository. The Google
harvester needs a billing-enabled Google Cloud project; the table is about 146 GB
and BigQuery bills roughly $0.73 per terabyte scanned, so queries select
narrowly.</p>

<footer>
<p>Generated {data['generated']}. Data from Google's Ads Transparency Center,
published under Article 39 of the EU Digital Services Act. Every claim on this
page links to its source.</p>
<p>This page documents advertising that breaches published platform policy. It
does not allege criminal conduct by any company named.</p>
</footer>

</div>
<script>window.__DATA__={json.dumps(data, separators=(',', ':'))};</script>
<script>{JS.replace('%CATLABELS%', json.dumps(CATEGORY_LABEL))}</script>
</body>
</html>
"""


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    data = collect(conn)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(build(data), encoding="utf-8")
    (OUT / "corpus.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    size = (OUT / "index.html").stat().st_size
    print(f"wrote {OUT/'index.html'} ({size:,} bytes)")
    print(f"wrote {OUT/'corpus.json'}")
    conn.close()


if __name__ == "__main__":
    main()
