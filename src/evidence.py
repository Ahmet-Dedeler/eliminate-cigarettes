"""
Turn the harvested ad corpus into evidence packets.

Each packet names one advertiser, lists the specific creatives attributable to
it, cites the exact policy clause the ads breach, and formats the whole thing
for the relevant complaint channel.

Deliberate design constraints, because this is accusatory output:

  * Every claim traces to a platform-published record with a permanent URL.
  * We report what the platform's own archive says, and the platform's own
    published policy. We do not editorialise beyond that.
  * Advertisers matched only on an ambiguous token are held back for review
    rather than published.
  * "Last shown" is reported as-is; an ad that stopped running months ago is
    labelled historical, not live.

Nothing here files anything. Generating a packet and submitting it are separate
steps, and submission is a human decision.
"""

from __future__ import annotations

import argparse
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "ads.db"
OUT_DIR = ROOT / "evidence"

POLICY = {
    "google": {
        "name": "Google Ads policy - Alcohol, tobacco and gambling",
        "clause": "Ads for tobacco or any products containing tobacco are not allowed.",
        "url": "https://support.google.com/adspolicy/answer/16489929",
        "notes": "No cessation carve-out and no country exceptions.",
    },
    "tiktok": {
        "name": "TikTok Advertising Policies - Dangerous Products or Services",
        "clause": (
            "We do not allow ad content and landing pages to show, promote, "
            "or sell tobacco, nicotine, or related products."
        ),
        "url": "https://ads.tiktok.com/help/article/tiktok-ads-policy-dangerous-products-or-services",
        "notes": (
            "TikTok's separate Branded Content Policy (eff. April 2026) is "
            "stricter still and prohibits even nicotine replacement products."
        ),
    },
}

# Corporate families, so subsidiaries roll up to the parent that controls them.
FAMILIES = {
    "British American Tobacco": ["british american tobacco", "velo marketing", "skruf snus"],
    "Japan Tobacco": ["japan tobacco"],
    "Imperial Brands": ["imperial tobacco"],
    "Philip Morris International": ["philip morris international"],
}


def family_for(advertiser: str) -> str | None:
    low = (advertiser or "").lower()
    for parent, patterns in FAMILIES.items():
        if any(p in low for p in patterns):
            return parent
    return None


def is_live(last_shown: str | None, window_days: int = 60) -> bool:
    if not last_shown:
        return False
    try:
        d = datetime.strptime(last_shown[:10], "%Y-%m-%d").date()
    except ValueError:
        return False
    return d >= date.today() - timedelta(days=window_days)


def load_google(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        "SELECT * FROM google_ads ORDER BY last_shown DESC"
    ).fetchall()


def render_advertiser(rows: list[sqlite3.Row], platform: str = "google") -> str:
    head = rows[0]
    pol = POLICY[platform]
    live = [r for r in rows if is_live(r["last_shown"])]
    regions = sorted({r for row in rows for r in (row["regions"] or "").split(",") if r})
    parent = family_for(head["advertiser"])

    lines = [
        f"### {head['advertiser']}",
        "",
        f"- **Registered legal name:** {head['advertiser_legal'] or 'not disclosed'}",
        f"- **Advertiser location:** {head['advertiser_hq'] or 'not disclosed'}",
        f"- **Google advertiser verification:** {head['verification'] or 'unknown'}",
    ]
    if parent:
        lines.append(f"- **Corporate parent:** {parent}")
    lines += [
        f"- **Creatives in archive:** {len(rows)}",
        f"- **Currently running (shown in last 60 days):** {len(live)}",
        f"- **Regions served:** {len(regions)} ({', '.join(regions[:12])}"
        + (", ..." if len(regions) > 12 else "") + ")",
        f"- **Most recent ad shown:** {head['last_shown'] or 'unknown'}",
        "",
        f"**Policy breached:** {pol['clause']}",
        f"Source: {pol['url']}",
        "",
        "**Sample creatives (permanent Google-hosted evidence links):**",
        "",
    ]
    for r in rows[:8]:
        lines.append(
            f"- `{r['creative_id']}` - last shown {r['last_shown']} - {r['creative_url']}"
        )
    if len(rows) > 8:
        lines.append(f"- ...and {len(rows) - 8} further creatives in the corpus.")
    lines.append("")
    return "\n".join(lines)


def build_report(conn: sqlite3.Connection) -> str:
    rows = load_google(conn)
    by_adv: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for r in rows:
        by_adv[r["advertiser"]].append(r)

    ordered = sorted(by_adv.items(), key=lambda kv: len(kv[1]), reverse=True)
    big4 = [(a, rs) for a, rs in ordered if family_for(a)]
    others = [(a, rs) for a, rs in ordered if not family_for(a)]

    total_live = sum(1 for r in rows if is_live(r["last_shown"]))
    pol = POLICY["google"]

    out = [
        "# Nicotine advertising on Google: evidence corpus",
        "",
        f"Generated {date.today().isoformat()} from "
        "`bigquery-public-data.google_ads_transparency_center`, the public ad "
        "archive Google publishes under Article 39 of the EU Digital Services Act.",
        "",
        "## Summary",
        "",
        f"- **{len(rows)}** tobacco/nicotine creatives identified",
        f"- **{len(by_adv)}** distinct advertisers",
        f"- **{total_live}** creatives shown within the last 60 days",
        f"- **{len(big4)}** advertisers are subsidiaries of Big Tobacco companies",
        "",
        f"Google's published policy states: *\"{pol['clause']}\"* {pol['notes']} "
        f"({pol['url']})",
        "",
        "Every record below is drawn from Google's own archive and links to a "
        "Google-hosted permanent page for the creative. No inference is applied "
        "beyond matching the advertiser's registered name.",
        "",
        "## Part 1 - Big Tobacco subsidiaries",
        "",
    ]
    for _, rs in big4:
        out.append(render_advertiser(rs))

    out += ["## Part 2 - Other tobacco and nicotine advertisers", ""]
    for _, rs in others[:40]:
        out.append(render_advertiser(rs))

    out += [
        "## Method and limitations",
        "",
        "- Advertisers are matched on their **registered name** as disclosed to "
        "Google, not on ad creative content. This is high-precision and "
        "low-recall: it will miss any advertiser whose name does not name the "
        "product, which is likely the majority of the grey market.",
        "- Known false positives are excluded by hand. For example *Philip "
        "Morris & Son* is a British countrywear retailer in Hereford with no "
        "connection to Philip Morris International, and is excluded.",
        "- `last_shown` reflects Google's archive, which updates daily. An ad "
        "listed as running may have stopped since the harvest.",
        "- This corpus covers **paid advertising only**. It says nothing about "
        "organic or influencer promotion, which is the larger surface and is "
        "explicitly out of scope for the only comparable continuous monitor "
        "(Vital Strategies' Canary).",
        "",
    ]
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(OUT_DIR / "google-corpus.md"))
    args = ap.parse_args()

    conn = sqlite3.connect(DB_PATH)
    report = build_report(conn)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")
    print(f"wrote {path} ({len(report):,} chars)")


if __name__ == "__main__":
    main()
