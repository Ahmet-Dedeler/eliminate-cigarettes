"""
Harvest tobacco/nicotine advertising from Google's Ads Transparency Center.

Google publishes every ad it serves in a public BigQuery dataset
(`bigquery-public-data.google_ads_transparency_center`, ~170M creatives,
refreshed daily) because the EU Digital Services Act Art. 39 requires it.

Google's advertising policy is the strictest of the major platforms:

    "Ads for tobacco or any products containing tobacco are not allowed."
    -- https://support.google.com/adspolicy/answer/16489929

There is no cessation carve-out and no country exception. So a tobacco or
nicotine advertiser appearing in this dataset is, on Google's own published
record, running ads Google's own policy prohibits.

Costs money to run: the table is ~146 GB and BigQuery bills ~$0.73/TB scanned.
We select narrowly and filter early to keep each sweep well under a dollar.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ads.db"
TABLE = "bigquery-public-data.google_ads_transparency_center.creative_stats"

# Advertiser-name patterns. Split into two tiers because precision matters more
# than recall here -- a false accusation against an unrelated company is far
# more damaging than a missed ad.
#
# CONFIRMED: corporate entities whose tobacco/nicotine business is unambiguous
# from the registered legal name alone.
CONFIRMED_PATTERNS = [
    "british american tobacco",
    "japan tobacco",
    "imperial tobacco",
    "philip morris international",
    "velo marketing",
    "skruf snus",
    "snusbolaget",
    "%snus%",          # snus is a tobacco product; the word has no other meaning
    "%nicotine%",
    "%e-cigarette%",
    "%vape%",
]

# KNOWN FALSE POSITIVES: names that match the patterns above but are not
# tobacco companies. Checked by hand; extend as the corpus grows.
#
# "Philip Morris & Son" is a British countrywear and outdoor clothing retailer
# based in Hereford (philipmorrisdirect.co.uk). It has no connection to Philip
# Morris International. Matching on "philip morris" alone would libel them.
EXCLUDE_EXACT = {
    "philip morris & son",
    "philip morris and son",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS google_ads (
    creative_id       TEXT PRIMARY KEY,
    advertiser_id     TEXT,
    advertiser        TEXT,
    advertiser_legal  TEXT,
    advertiser_hq     TEXT,
    verification      TEXT,
    creative_url      TEXT,
    ad_format         TEXT,
    topic             TEXT,
    regions           TEXT,
    n_regions         INTEGER,
    first_shown       TEXT,
    last_shown        TEXT,
    harvested_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_g_advertiser ON google_ads(advertiser);
CREATE INDEX IF NOT EXISTS idx_g_last_shown ON google_ads(last_shown);
"""


def build_query(limit: int) -> str:
    likes = " OR ".join(
        f'LOWER(advertiser_disclosed_name) LIKE "{p if "%" in p else f"%{p}%"}"'
        for p in CONFIRMED_PATTERNS
    )
    excludes = ", ".join(f'"{e}"' for e in EXCLUDE_EXACT)
    return f"""
SELECT
  creative_id,
  advertiser_id,
  advertiser_disclosed_name AS advertiser,
  advertiser_legal_name     AS advertiser_legal,
  advertiser_location       AS advertiser_hq,
  advertiser_verification_status AS verification,
  creative_page_url         AS creative_url,
  ad_format_type            AS ad_format,
  topic,
  ARRAY_TO_STRING(ARRAY(SELECT rs.region_code FROM UNNEST(region_stats) rs), ",") AS regions,
  ARRAY_LENGTH(region_stats) AS n_regions,
  (SELECT MIN(rs.first_shown) FROM UNNEST(region_stats) rs) AS first_shown,
  (SELECT MAX(rs.last_shown)  FROM UNNEST(region_stats) rs) AS last_shown
FROM `{TABLE}`
WHERE ({likes})
  AND LOWER(TRIM(advertiser_disclosed_name)) NOT IN ({excludes})
ORDER BY last_shown DESC
LIMIT {limit}
"""


def run_bq(query: str, project: str, account: str) -> list[dict]:
    proc = subprocess.run(
        [
            "bq", f"--project_id={project}", "query", "--nouse_legacy_sql",
            "--format=json", f"--max_rows={200000}", query,
        ],
        capture_output=True, text=True,
        env={**__import__("os").environ, "CLOUDSDK_CORE_ACCOUNT": account},
    )
    if proc.returncode != 0:
        raise RuntimeError(f"bq failed: {proc.stderr[-2000:]}")
    # bq prints progress lines before the JSON payload
    out = proc.stdout
    start = out.find("[")
    return json.loads(out[start:]) if start >= 0 else []


def store(rows: list[dict]) -> int:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    now = datetime.now(timezone.utc).isoformat()
    cols = [
        "creative_id", "advertiser_id", "advertiser", "advertiser_legal",
        "advertiser_hq", "verification", "creative_url", "ad_format", "topic",
        "regions", "n_regions", "first_shown", "last_shown", "harvested_at",
    ]
    conn.executemany(
        f"INSERT OR REPLACE INTO google_ads ({','.join(cols)}) "
        f"VALUES ({','.join('?' for _ in cols)})",
        [tuple(r.get(c) if c != "harvested_at" else now for c in cols) for r in rows],
    )
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM google_ads").fetchone()[0]
    conn.close()
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", default="find-domains-485101")
    ap.add_argument("--account", default="ahmetdedelerr@gmail.com")
    ap.add_argument("--limit", type=int, default=50000)
    args = ap.parse_args()

    print("querying Google Ads Transparency Center...")
    rows = run_bq(build_query(args.limit), args.project, args.account)
    print(f"  returned {len(rows)} creatives")
    total = store(rows)
    print(f"  database now holds {total} Google creatives")


if __name__ == "__main__":
    main()
