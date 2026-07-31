"""
Harvest nicotine/tobacco advertising from TikTok's Commercial Content Library.

The library exists because the EU Digital Services Act (Art. 39) requires very
large platforms to publish a public repository of every ad they serve. TikTok's
own advertising policy prohibits nicotine advertising outright:

    "We do not allow ad content and landing pages to show, promote, or sell
     tobacco, nicotine, or related products."
    -- https://ads.tiktok.com/help/article/tiktok-ads-policy-dangerous-products-or-services

So every nicotine ad found in this archive is a violation that TikTok has itself
published. We harvest, dedupe, and archive them as evidence.

Uses the library's own web UI endpoint. Unauthenticated, but requires the
`X-CCL-STR` header carrying a config string from /support-regions -- without it
the API returns HTTP 421. Rate limit is roughly 12 requests per IP before a
route-specific cooldown of ~5 minutes, so we throttle deliberately.
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

import requests

BASE = "https://library.tiktok.com/api/v1"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# Search terms, deliberately multilingual. The archive is EEA+UK+CH+TR, so
# English-only querying badly undercounts. "puff" and "snus" carry most of the
# grey-market volume; brand terms catch the Big 4 subsidiaries directly.
TERMS_GENERIC = ["vape", "puff", "nicotine", "e-cigarette", "snus", "nikotin", "cigarette"]
TERMS_BRAND = ["velo", "zyn", "vuse", "iqos", "elfbar", "lost mary", "glo", "nordic spirit"]

# Terms that are ambiguous in some languages and need classifier confirmation
# rather than being trusted on keyword match alone. "velo" is French for bicycle;
# "puff" is a common English word; "glo" appears in unrelated brand names.
AMBIGUOUS = {"velo", "puff", "glo", "zyn"}

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ads.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS ads (
    ad_id            TEXT PRIMARY KEY,
    platform         TEXT NOT NULL,
    region           TEXT NOT NULL,
    advertiser       TEXT,
    advertiser_id    TEXT,
    ad_text          TEXT,
    first_shown      TEXT,
    last_shown       TEXT,
    video_url        TEXT,
    audience_size    TEXT,
    matched_term     TEXT,
    ambiguous        INTEGER DEFAULT 0,
    raw              TEXT,
    harvested_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ads_region     ON ads(region);
CREATE INDEX IF NOT EXISTS idx_ads_advertiser ON ads(advertiser);
CREATE INDEX IF NOT EXISTS idx_ads_last_shown ON ads(last_shown);

CREATE TABLE IF NOT EXISTS harvest_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    region       TEXT,
    term         TEXT,
    total_hits   INTEGER,
    fetched      INTEGER,
    ran_at       TEXT
);
"""


@dataclass
class Ad:
    ad_id: str
    platform: str
    region: str
    advertiser: str
    advertiser_id: str
    ad_text: str
    first_shown: str
    last_shown: str
    video_url: str
    audience_size: str
    matched_term: str
    ambiguous: int
    raw: str
    harvested_at: str


class RateLimited(Exception):
    """Raised when the library returns its route-level cooldown response."""


class TikTokLibrary:
    def __init__(self, cooldown: float = 6.0):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": UA, "Content-Type": "application/json"})
        self.cooldown = cooldown
        self._config_str: str | None = None

    @property
    def config_str(self) -> str:
        """The X-CCL-STR header value. Fetched once, reused for the session."""
        if self._config_str is None:
            r = self.session.get(f"{BASE}/support-regions", timeout=30)
            r.raise_for_status()
            self._config_str = r.json()["config_str"]
        return self._config_str

    def search(
        self, region: str, term: str, days: int = 365, limit: int = 50, offset: int = 0
    ) -> dict:
        now = datetime.now(timezone.utc)
        params = {
            "region": region,
            "type": "1",
            "start_time": int((now - timedelta(days=days)).timestamp()),
            "end_time": int(now.timestamp()),
        }
        body = {
            "query_type": "1",
            "order": "last_shown_date,desc",
            "offset": offset,
            "limit": limit,
            "search_clause": {"search_terms": [term], "search_type": 1},
        }
        r = self.session.post(
            f"{BASE}/search",
            params=params,
            json=body,
            headers={"X-CCL-STR": self.config_str},
            timeout=45,
        )
        # 421 (Misdirected) and 425 (Too Early) are both used as route-level
        # cooldown signals; 429 in case they ever switch to the standard one.
        if r.status_code in (421, 425, 429):
            raise RateLimited(f"http {r.status_code} cooldown on {region}/{term}")
        r.raise_for_status()
        payload = r.json()
        # code 0 is success; the library reuses non-zero codes for its cooldown
        if payload.get("code") not in (0, None):
            raise RateLimited(f"api code {payload.get('code')}: {payload.get('msg')}")
        return payload

    def paginate(
        self, region: str, term: str, max_ads: int, days: int = 365
    ) -> Iterator[dict]:
        """Yield raw ad dicts, backing off politely when rate limited."""
        offset, seen, total = 0, 0, None
        while seen < max_ads:
            for attempt in range(4):
                try:
                    payload = self.search(region, term, days=days, offset=offset)
                    break
                except RateLimited:
                    wait = 90 * (attempt + 1) + random.uniform(0, 20)
                    print(
                        f"    rate limited on {region}/{term}, waiting {wait:.0f}s",
                        file=sys.stderr,
                    )
                    time.sleep(wait)
            else:
                print(f"    giving up on {region}/{term}", file=sys.stderr)
                return

            # Top-level shape: {"data": [...], "total": N, "has_more": bool}
            ads = payload.get("data") or []
            if total is None:
                total = payload.get("total") or 0
                print(f"    {region}/{term}: {total} ads in archive")
            if not ads:
                return
            for ad in ads:
                yield ad
                seen += 1
                if seen >= max_ads:
                    return
            if not payload.get("has_more"):
                return
            offset += len(ads)
            time.sleep(self.cooldown + random.uniform(0, 2))


def _epoch_ms_to_iso(value) -> str:
    """The library reports show dates as epoch milliseconds."""
    try:
        ms = int(value)
    except (TypeError, ValueError):
        return ""
    if ms <= 0:
        return ""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat()


def normalize(raw: dict, region: str, term: str) -> Ad:
    """Flatten a library record into our schema."""
    videos = raw.get("videos") or []
    video_url = videos[0].get("video_url", "") if videos else ""
    # Some records carry stills instead of video
    if not video_url:
        images = raw.get("image_urls") or []
        video_url = images[0] if images else ""

    return Ad(
        ad_id=str(raw.get("id", "")),
        platform="tiktok",
        region=region,
        # `name` is the advertiser handle, which is also the TikTok account name
        advertiser=str(raw.get("name", "")),
        advertiser_id=str(raw.get("advertiser_id", "")),
        ad_text=str(raw.get("title", "")),
        first_shown=_epoch_ms_to_iso(raw.get("first_shown_date")),
        last_shown=_epoch_ms_to_iso(raw.get("last_shown_date")),
        video_url=video_url,
        audience_size=str(raw.get("estimated_audience", "")),
        matched_term=term,
        ambiguous=int(term.lower() in AMBIGUOUS),
        raw=json.dumps(raw, ensure_ascii=False),
        harvested_at=datetime.now(timezone.utc).isoformat(),
    )


def init_db(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def store(conn: sqlite3.Connection, ads: list[Ad]) -> int:
    if not ads:
        return 0
    cols = list(asdict(ads[0]).keys())
    sql = (
        f"INSERT OR REPLACE INTO ads ({','.join(cols)}) "
        f"VALUES ({','.join('?' for _ in cols)})"
    )
    conn.executemany(sql, [tuple(asdict(a).values()) for a in ads])
    conn.commit()
    return len(ads)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--regions", default="FR,DE,IT,ES,GB,PL,NL,SE",
                    help="comma-separated region codes")
    ap.add_argument("--terms", default=",".join(TERMS_GENERIC + TERMS_BRAND))
    ap.add_argument("--max-per-query", type=int, default=100)
    ap.add_argument("--days", type=int, default=365)
    args = ap.parse_args()

    regions = [r.strip().upper() for r in args.regions.split(",") if r.strip()]
    terms = [t.strip() for t in args.terms.split(",") if t.strip()]

    lib = TikTokLibrary()
    conn = init_db()
    grand_total = 0

    for region in regions:
        for term in terms:
            batch = []
            try:
                for raw in lib.paginate(region, term, args.max_per_query, args.days):
                    batch.append(normalize(raw, region, term))
            except Exception as exc:  # keep the sweep alive across single failures
                print(f"    error {region}/{term}: {exc}", file=sys.stderr)
            n = store(conn, batch)
            grand_total += n
            conn.execute(
                "INSERT INTO harvest_log (region, term, total_hits, fetched, ran_at) "
                "VALUES (?,?,?,?,?)",
                (region, term, None, n, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            if n:
                print(f"  stored {n:>4} for {region}/{term}")

    total_rows = conn.execute("SELECT COUNT(*) FROM ads").fetchone()[0]
    advertisers = conn.execute(
        "SELECT COUNT(DISTINCT advertiser) FROM ads WHERE advertiser != ''"
    ).fetchone()[0]
    print(f"\nharvested {grand_total} rows this run")
    print(f"database now holds {total_rows} ads from {advertisers} advertisers")


if __name__ == "__main__":
    main()
