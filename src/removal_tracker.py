"""
Measure whether reporting an ad actually gets it removed.

No published study has done this. The literature documents nicotine marketing
at length and then stops; the reporting step and its outcome are simply absent.
So the question "does reporting work, and how fast" has no empirical answer.

Design. Reported creatives alone prove nothing, because ad campaigns end on
their own -- an ad that vanishes two weeks after a complaint may have simply
run its course. So every reported creative is paired with a **control**: a
creative from the same advertiser, same category, and closest available
impression volume, which is deliberately NOT reported. Removal rates are then
compared between arms.

Outcome is read from Google's own data rather than from anything we assert:

  * still present in `creative_stats` with an advancing `last_shown` -> running
  * present but `last_shown` frozen                                  -> stopped
  * absent from `creative_stats`                                     -> withdrawn
  * present in `removed_creative_stats`                              -> removed
    by Google, and that table gives the removal reason and whether it was
    detected by automated means

The fourth case is the one that matters: it distinguishes a policy takedown
from an advertiser simply ending a campaign.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "ads.db"
PROJECT = "find-domains-485101"
ACCOUNT = "ahmetdedelerr@gmail.com"

LIVE_TABLE = "bigquery-public-data.google_ads_transparency_center.creative_stats"
REMOVED_TABLE = ("bigquery-public-data.google_ads_transparency_center."
                 "removed_creative_stats")

SCHEMA = """
CREATE TABLE IF NOT EXISTS experiment (
    creative_id   TEXT PRIMARY KEY,
    advertiser    TEXT NOT NULL,
    category      TEXT NOT NULL,
    arm           TEXT NOT NULL,          -- 'reported' | 'control'
    pair_id       INTEGER,                -- links a reported/control pair
    baseline_last_shown TEXT,
    baseline_impressions INTEGER,
    creative_url  TEXT,
    enrolled_at   TEXT NOT NULL,
    reported_at   TEXT,
    report_channel TEXT
);

CREATE TABLE IF NOT EXISTS observation (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    creative_id   TEXT NOT NULL,
    observed_at   TEXT NOT NULL,
    state         TEXT NOT NULL,          -- running|stopped|withdrawn|removed
    last_shown    TEXT,
    removal_reason     TEXT,
    violation_category TEXT,
    automated     INTEGER,
    UNIQUE(creative_id, observed_at)
);
CREATE INDEX IF NOT EXISTS idx_obs_creative ON observation(creative_id);
"""


def bq(query: str) -> list[dict]:
    proc = subprocess.run(
        ["bq", f"--project_id={PROJECT}", "query", "--nouse_legacy_sql",
         "--format=json", "--max_rows=200000", query],
        capture_output=True, text=True,
        env={**os.environ, "CLOUDSDK_CORE_ACCOUNT": ACCOUNT},
    )
    if proc.returncode != 0:
        raise RuntimeError(f"bq failed: {proc.stderr[-1500:]}")
    out = proc.stdout
    i = out.find("[")
    return json.loads(out[i:]) if i >= 0 else []


# Only enrol categories where Google's own policy text actually covers the
# product. Reporting a nicotine pouch under a tobacco clause would be a weak
# claim, and a weak claim contaminates the experiment.
# Narrowed after manual inspection. "mixed_nicotine" was dropped because
# spot-checking BAT Austria's live creatives showed them to be VELO nicotine
# POUCH ads ("Teste jetzt die VELO Nicotine Pouches"), which Google's policy
# does not cover and which are lawful to advertise in Austria until Feb 2028.
# Reporting those would be a losing claim and would contaminate the experiment.
#
# Snus is the strongest cell available: Google's policy names "snus" outright,
# and Directive 2003/33/EC art. 3(2) prohibits the advertising across the EEA.
ELIGIBLE_CATEGORIES = ("snus_oral_tobacco", "vape_ends", "combustible_tobacco")


def enrol(conn: sqlite3.Connection, n_pairs: int, seed: int = 20260731) -> int:
    """Pick matched reported/control pairs from the same advertiser."""
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    rng = random.Random(seed)
    now = datetime.now(timezone.utc).isoformat()

    placeholders = ",".join("?" for _ in ELIGIBLE_CATEGORIES)
    rows = conn.execute(
        f"""
        SELECT g.creative_id, g.advertiser, g.creative_url, g.last_shown,
               COALESCE(g.impressions_floor, 0) AS imp, ac.category
        FROM google_ads g
        JOIN advertiser_class ac ON ac.advertiser = g.advertiser
        WHERE ac.category IN ({placeholders})
          AND ac.confidence = 'verified'
          AND g.last_shown >= date('now', '-45 day')
        ORDER BY g.advertiser, imp DESC
        """,
        ELIGIBLE_CATEGORIES,
    ).fetchall()

    by_adv: dict[str, list[sqlite3.Row]] = {}
    for r in rows:
        by_adv.setdefault(r["advertiser"], []).append(r)

    # Only advertisers with at least two live creatives can supply a pair.
    eligible = {a: rs for a, rs in by_adv.items() if len(rs) >= 2}
    if not eligible:
        return 0

    pairs, pair_id = [], 0
    advertisers = sorted(eligible)
    # Round-robin so no single advertiser dominates the sample.
    while len(pairs) < n_pairs:
        progressed = False
        for adv in advertisers:
            pool = eligible[adv]
            if len(pool) < 2 or len(pairs) >= n_pairs:
                continue
            # Match on adjacent impression volume so the arms are comparable.
            idx = rng.randrange(0, len(pool) - 1)
            a, b = pool[idx], pool[idx + 1]
            for x in (a, b):
                pool.remove(x)
            pair_id += 1
            pairs.append((pair_id, a, b))
            progressed = True
        if not progressed:
            break

    for pid, reported, control in pairs:
        for row, arm in ((reported, "reported"), (control, "control")):
            conn.execute(
                "INSERT OR IGNORE INTO experiment (creative_id, advertiser, "
                "category, arm, pair_id, baseline_last_shown, "
                "baseline_impressions, creative_url, enrolled_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (row["creative_id"], row["advertiser"], row["category"], arm,
                 pid, row["last_shown"], row["imp"], row["creative_url"], now),
            )
    conn.commit()
    return len(pairs)


def observe(conn: sqlite3.Connection) -> dict:
    """Re-check every enrolled creative against Google's current data."""
    conn.row_factory = sqlite3.Row
    ids = [r["creative_id"] for r in conn.execute(
        "SELECT creative_id FROM experiment").fetchall()]
    if not ids:
        return {}
    quoted = ",".join(f'"{i}"' for i in ids)
    now = datetime.now(timezone.utc).isoformat()

    live = {r["creative_id"]: r for r in bq(f"""
        SELECT creative_id,
               (SELECT MAX(rs.last_shown) FROM UNNEST(region_stats) rs) AS last_shown
        FROM `{LIVE_TABLE}`
        WHERE creative_id IN ({quoted})
    """)}

    # removed_creative_stats has no creative_id column, only the page URL,
    # which embeds the id -- so match on the URL suffix.
    removed = {}
    for r in bq(f"""
        SELECT creative_page_url,
               (SELECT d.removal_reason FROM UNNEST(disapproval) d LIMIT 1) AS removal_reason,
               (SELECT d.violation_category FROM UNNEST(disapproval) d LIMIT 1) AS violation_category,
               (SELECT d.use_of_automated_means FROM UNNEST(disapproval) d LIMIT 1) AS automated
        FROM `{REMOVED_TABLE}`
        WHERE REGEXP_EXTRACT(creative_page_url, r'creative/(CR[0-9]+)') IN ({quoted})
    """):
        cid = (r["creative_page_url"] or "").rsplit("/", 1)[-1]
        removed[cid] = r

    counts: dict[str, int] = {}
    for row in conn.execute("SELECT * FROM experiment").fetchall():
        cid = row["creative_id"]
        if cid in removed:
            rem = removed[cid]
            state, last = "removed", None
            reason = rem.get("removal_reason")
            viol = rem.get("violation_category")
            auto = 1 if rem.get("automated") else 0
        elif cid in live:
            last = live[cid]["last_shown"]
            state = "running" if last and last > (row["baseline_last_shown"] or "") \
                else "stopped"
            reason = viol = None
            auto = None
        else:
            state, last, reason, viol, auto = "withdrawn", None, None, None, None

        conn.execute(
            "INSERT OR IGNORE INTO observation (creative_id, observed_at, state, "
            "last_shown, removal_reason, violation_category, automated) "
            "VALUES (?,?,?,?,?,?,?)",
            (cid, now, state, last, reason, viol, auto),
        )
        counts[f"{row['arm']}/{state}"] = counts.get(f"{row['arm']}/{state}", 0) + 1
    conn.commit()
    return counts


def report_summary(conn: sqlite3.Connection) -> str:
    conn.row_factory = sqlite3.Row
    enrolled = conn.execute(
        "SELECT arm, COUNT(*) n FROM experiment GROUP BY arm").fetchall()
    reported = conn.execute(
        "SELECT COUNT(*) n FROM experiment WHERE reported_at IS NOT NULL"
    ).fetchone()["n"]
    latest = conn.execute(
        "SELECT MAX(observed_at) m FROM observation").fetchone()["m"]

    lines = ["Removal experiment", ""]
    for r in enrolled:
        lines.append(f"  {r['arm']:<9} enrolled: {r['n']}")
    lines.append(f"  actually reported so far: {reported}")
    if not latest:
        lines.append("  no observations yet")
        return "\n".join(lines)

    lines += ["", f"  latest observation {latest}", ""]
    for r in conn.execute(
        "SELECT e.arm, o.state, COUNT(*) n FROM observation o "
        "JOIN experiment e ON e.creative_id = o.creative_id "
        "WHERE o.observed_at = ? GROUP BY 1,2 ORDER BY 1,2", (latest,)
    ):
        lines.append(f"    {r['arm']:<9} {r['state']:<10} {r['n']:>4}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["enrol", "observe", "summary"])
    ap.add_argument("--pairs", type=int, default=40)
    args = ap.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    if args.command == "enrol":
        n = enrol(conn, args.pairs)
        print(f"enrolled {n} matched pairs ({n*2} creatives)")
    elif args.command == "observe":
        counts = observe(conn)
        for k in sorted(counts):
            print(f"  {k:<24} {counts[k]}")
    print()
    print(report_summary(conn))
    conn.close()


if __name__ == "__main__":
    main()
