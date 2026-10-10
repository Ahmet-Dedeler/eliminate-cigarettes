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

Output formats (--format):

  md    one combined Markdown corpus (default, unchanged)
  html  one self-contained, print-ready HTML dossier per advertiser
  pdf   the same dossiers rendered to PDF (needs `pip install weasyprint`)

Dossiers show the advertiser ID, the policy clause breached and the creatives.
If a screenshot named <creative_id>.png/.jpg/.webp exists in
evidence/screenshots/ it is embedded; otherwise the permanent Google link is
shown. Nothing is fetched from the network and no screenshot is fabricated.
"""

from __future__ import annotations

import argparse
import base64
import html
import re
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "ads.db"
OUT_DIR = ROOT / "evidence"
SCREENSHOT_DIR = OUT_DIR / "screenshots"
MAX_SCREENSHOT_BYTES = 1_500_000

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


def load_google(
    conn: sqlite3.Connection, include_likely: bool = False
) -> list[sqlite3.Row]:
    """Load creatives for advertisers that passed classification.

    Only advertisers with confidence 'verified' are returned by default, so
    false positives (category 'not_nicotine') and quarantined or merely
    'likely' advertisers never reach an evidence packet. Pass
    include_likely=True to also include 'likely' rows for internal review.
    Run `python3 src/classify.py` first to populate advertiser_class.
    """
    conn.row_factory = sqlite3.Row
    has_class = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='advertiser_class'"
    ).fetchone()
    if not has_class:
        raise SystemExit(
            "advertiser_class table not found. Run `python3 src/classify.py` "
            "(and optionally verify_advertisers.py) before generating evidence."
        )
    confidences = ("verified", "likely") if include_likely else ("verified",)
    marks = ",".join("?" for _ in confidences)
    return conn.execute(
        "SELECT g.* FROM google_ads g "
        "JOIN advertiser_class c ON c.advertiser = g.advertiser "
        f"WHERE c.category != 'not_nicotine' AND c.confidence IN ({marks}) "
        "ORDER BY g.last_shown DESC",
        confidences,
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


def build_report(conn: sqlite3.Connection, include_likely: bool = False) -> str:
    rows = load_google(conn, include_likely)
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
        "- Only advertisers classified `verified` are included; false positives "
        "and unconfirmed advertisers are filtered out via `advertiser_class`. "
        "For example *Philip "
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


# ---------------------------------------------------------------------------
# HTML / PDF dossiers
# ---------------------------------------------------------------------------

DOSSIER_CSS = """
@page { size: A4; margin: 18mm 16mm; }
* { box-sizing: border-box; }
body { font: 11pt/1.5 Georgia, 'Times New Roman', serif; color: #1a1a18; margin: 0; }
h1 { font-size: 20pt; margin: 0 0 4pt; }
h2 { font-size: 13pt; margin: 18pt 0 6pt; border-top: 1px solid #ccc; padding-top: 10pt; }
.sub { color: #555; margin: 0 0 12pt; font-size: 10pt; }
table { width: 100%; border-collapse: collapse; font: 9pt/1.4 Helvetica, Arial, sans-serif; }
th { text-align: left; background: #f3f1ec; padding: 5pt 6pt; border-bottom: 1.5px solid #bbb; }
td { padding: 5pt 6pt; border-bottom: 1px solid #ddd; vertical-align: top; word-break: break-word; }
.kv td:first-child { width: 34%; color: #555; font-weight: 600; }
.policy { border-left: 3px solid #8c2f22; background: #f8efec; padding: 8pt 12pt; margin: 8pt 0; }
.policy blockquote { margin: 4pt 0; font-style: italic; }
.mono { font-family: Menlo, Consolas, monospace; font-size: 8pt; }
.shot { max-width: 100%; max-height: 90mm; border: 1px solid #ccc; display: block; margin-top: 4pt; }
.noshot { color: #888; font-style: italic; }
.note { font: 9pt/1.45 Helvetica, Arial, sans-serif; color: #444; }
tr, .policy { page-break-inside: avoid; }
"""

_SAFE_URL = re.compile(r"^https?://", re.I)


def esc(value: object) -> str:
    """HTML-escape any value; advertiser data is untrusted."""
    return html.escape("" if value is None else str(value), quote=True)


def safe_link(url: str | None) -> str:
    """Return an escaped href only for http(s) URLs, otherwise plain text."""
    if url and _SAFE_URL.match(url):
        return f'<a href="{esc(url)}">{esc(url)}</a>'
    return esc(url or "not available")


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "unknown").lower()).strip("-")[:80] or "unknown"


def find_screenshot(creative_id: str, shot_dir: Path) -> str | None:
    """Return a data: URI for a local screenshot of this creative, if any."""
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "", creative_id or "")
    if not safe_id:
        return None
    mimes = {".png": "image/png", ".jpg": "image/jpeg",
             ".jpeg": "image/jpeg", ".webp": "image/webp"}
    for ext, mime in mimes.items():
        path = shot_dir / f"{safe_id}{ext}"
        if path.is_file() and path.stat().st_size <= MAX_SCREENSHOT_BYTES:
            data = base64.b64encode(path.read_bytes()).decode("ascii")
            return f"data:{mime};base64,{data}"
    return None


def render_dossier_html(
    rows: list[sqlite3.Row],
    platform: str = "google",
    shot_dir: Path = SCREENSHOT_DIR,
    max_creatives: int = 25,
) -> str:
    """One self-contained, print-ready HTML dossier for a single advertiser."""
    head = rows[0]
    pol = POLICY[platform]
    live = [r for r in rows if is_live(r["last_shown"])]
    regions = sorted({x for row in rows for x in (row["regions"] or "").split(",") if x})
    parent = family_for(head["advertiser"])
    firsts = [r["first_shown"] for r in rows if r["first_shown"]]
    harvested = max((r["harvested_at"] or "" for r in rows), default="")

    def kv(label: str, value: object) -> str:
        return f"<tr><td>{esc(label)}</td><td>{esc(value)}</td></tr>"

    details = "".join([
        kv("Advertiser", head["advertiser"]),
        kv("Advertiser ID", head["advertiser_id"] or "not disclosed"),
        kv("Registered legal name", head["advertiser_legal"] or "not disclosed"),
        kv("Advertiser location", head["advertiser_hq"] or "not disclosed"),
        kv("Platform advertiser verification", head["verification"] or "unknown"),
        kv("Corporate parent", parent or "none identified"),
        kv("Creatives in archive", len(rows)),
        kv("Shown in last 60 days", len(live)),
        kv("Regions served", f"{len(regions)} ({', '.join(regions)})"),
        kv("First shown", min(firsts) if firsts else "unknown"),
        kv("Most recent ad shown", head["last_shown"] or "unknown"),
        kv("Archive harvested at (UTC)", harvested or "unknown"),
    ])

    creative_rows = []
    for r in rows[:max_creatives]:
        shot = find_screenshot(r["creative_id"], shot_dir)
        shot_html = (f'<img class="shot" alt="Screenshot of creative {esc(r["creative_id"])}" '
                     f'src="{shot}">') if shot else (
            '<br><span class="noshot">No local screenshot; see permanent link.</span>')
        creative_rows.append(
            "<tr>"
            f'<td class="mono">{esc(r["creative_id"])}</td>'
            f'<td>{esc(r["ad_format"] or "")}</td>'
            f'<td>{esc(r["first_shown"] or "")}<br>{esc(r["last_shown"] or "")}</td>'
            f'<td>{safe_link(r["creative_url"])}{shot_html}</td>'
            "</tr>"
        )
    more = ""
    if len(rows) > max_creatives:
        more = (f'<p class="note">{len(rows) - max_creatives} further creatives for this '
                "advertiser are in the corpus and not listed here.</p>")

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Evidence dossier: {esc(head["advertiser"])}</title>
<style>{DOSSIER_CSS}</style></head><body>
<h1>{esc(head["advertiser"])}</h1>
<p class="sub">Evidence dossier generated {date.today().isoformat()} from the platform's own
public ad archive (EU Digital Services Act, Art. 39).</p>

<h2>Advertiser record</h2>
<table class="kv"><tbody>{details}</tbody></table>

<h2>Policy clause breached</h2>
<div class="policy">
<strong>{esc(pol["name"])}</strong>
<blockquote>&ldquo;{esc(pol["clause"])}&rdquo;</blockquote>
<div class="note">{esc(pol["notes"])}<br>Source: {safe_link(pol["url"])}</div>
</div>

<h2>Creatives</h2>
<table><thead><tr><th>Creative ID</th><th>Format</th><th>First / last shown</th>
<th>Permanent link and screenshot</th></tr></thead>
<tbody>{"".join(creative_rows)}</tbody></table>
{more}

<h2>Method and limits</h2>
<p class="note">The advertiser was matched on its registered name and classified
<em>verified</em>. This dossier documents a breach of the platform's advertising policy,
which is an agreement between advertiser and platform; it does not allege criminal conduct,
and the advertising may be lawful where it ran. Dates are as reported by the archive and an
ad listed as running may have stopped since harvest. Review before any submission;
submission is a human decision.</p>
</body></html>
"""


def write_dossiers(
    conn: sqlite3.Connection,
    out_dir: Path,
    fmt: str = "html",
    include_likely: bool = False,
    only: str | None = None,
    max_creatives: int = 25,
    shot_dir: Path = SCREENSHOT_DIR,
) -> list[Path]:
    """Write one dossier per advertiser; returns the files written."""
    if fmt == "pdf":
        try:
            from weasyprint import HTML  # optional dependency
        except (ImportError, OSError) as exc:
            # OSError: WeasyPrint is installed but its native GTK/Pango
            # libraries are missing (common on Windows).
            raise SystemExit(
                f"PDF output is unavailable ({exc.__class__.__name__}). "
                "Install WeasyPrint with `pip install weasyprint` and, on Windows, "
                "its GTK libraries (see "
                "https://doc.courtbouillon.org/weasyprint/stable/first_steps.html).\n"
                "Or use --format html and print the file to PDF from a browser."
            )
    rows = load_google(conn, include_likely)
    by_adv: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for r in rows:
        if only and only.lower() not in (r["advertiser"] or "").lower():
            continue
        by_adv[r["advertiser"]].append(r)

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for adv, rs in sorted(by_adv.items(), key=lambda kv: len(kv[1]), reverse=True):
        doc = render_dossier_html(rs, "google", shot_dir, max_creatives)
        base = out_dir / f"{slugify(adv)}"
        if fmt == "pdf":
            path = base.with_suffix(".pdf")
            HTML(string=doc).write_pdf(str(path))
        else:
            path = base.with_suffix(".html")
            path.write_text(doc, encoding="utf-8")
        written.append(path)
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(OUT_DIR / "google-corpus.md"))
    ap.add_argument("--format", choices=["md", "html", "pdf"], default="md",
                    help="md: one corpus file; html/pdf: one dossier per advertiser")
    ap.add_argument("--dossier-dir", default=str(OUT_DIR / "dossiers"))
    ap.add_argument("--advertiser", help="only advertisers whose name contains this text")
    ap.add_argument("--max-creatives", type=int, default=25)
    ap.add_argument("--screenshots-dir", default=str(SCREENSHOT_DIR))
    ap.add_argument(
        "--include-likely", action="store_true",
        help="also include 'likely' (not yet hand-verified) advertisers; "
             "never use the output for a filing",
    )
    args = ap.parse_args()

    conn = sqlite3.connect(DB_PATH)
    if args.format in ("html", "pdf"):
        files = write_dossiers(
            conn, Path(args.dossier_dir), args.format, args.include_likely,
            args.advertiser, args.max_creatives, Path(args.screenshots_dir),
        )
        print(f"wrote {len(files)} {args.format} dossier(s) to {args.dossier_dir}")
        return
    report = build_report(conn, args.include_likely)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")
    print(f"wrote {path} ({len(report):,} chars)")


if __name__ == "__main__":
    main()