"""
Classify advertisers into product categories, and refuse to guess.

This module exists because naive substring matching on advertiser names is
catastrophically noisy. Real examples caught in the first sweep, all of which
would have been false accusations:

    Kjells Vapen AB          Swedish "vapen" = WEAPONS. A gun shop.
    Vapenprodukter Sverige   Same. Weapons products.
    SAS CARVAPEUR974         French "vapeur" = STEAM. Car steam-cleaning.
    CITEV ... TRAINS EXPRESS Heritage steam trains ("trains a vapeur").
    Innovapet GmbH           Pet supplies. "inno-VAPE-t".
    AkvaPet24 s.r.o.         Pet supplies. "ak-VAPE-t".
    NovaPeak e-commerce      Home and garden. "no-VAPE-ak".
    YUVAPEN                  Turkish PVC window manufacturer.
    Relevaperdite.com        Italian leak detection ("rileva perdite").
    Advelo Marketing         Estonian marketing agency, matched "velo marketing".

So classification runs in tiers, and anything not positively identified is
quarantined rather than published. The asymmetry is deliberate: a missed
advertiser costs us recall, a false one costs us the project.

Product categories are kept separate because they are regulated under different
instruments and breach different policy clauses. A tobacco-free nicotine pouch
is not a tobacco product, and citing a tobacco clause against one is a defect.
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ads.db"


class Category(str, Enum):
    COMBUSTIBLE = "combustible_tobacco"
    SNUS = "snus_oral_tobacco"
    POUCH = "nicotine_pouch"       # tobacco-FREE; regulated differently
    VAPE = "vape_ends"
    HEATED = "heated_tobacco"
    MIXED = "mixed_nicotine"        # sells several categories
    UNKNOWN = "unknown"
    NOT_NICOTINE = "not_nicotine"   # confirmed false positive


class Confidence(str, Enum):
    VERIFIED = "verified"    # known corporate entity, or manually confirmed
    LIKELY = "likely"        # strong signal, needs review before use
    QUARANTINE = "quarantine"  # ambiguous, never publish


# ---------------------------------------------------------------------------
# Tier A: known corporate entities.
#
# Matched on normalised name containing the key. These are registered tobacco
# and nicotine businesses whose identity is not in question.
# ---------------------------------------------------------------------------

BIG_TOBACCO = {
    "british american tobacco": ("British American Tobacco", Category.MIXED),
    "japan tobacco": ("Japan Tobacco", Category.MIXED),
    "imperial tobacco": ("Imperial Brands", Category.MIXED),
    "philip morris international": ("Philip Morris International", Category.MIXED),
    # BAT's tobacco-free nicotine pouch brand. Separate legal entity, and the
    # product contains no tobacco, which matters for which clause applies.
    "velo marketing": ("British American Tobacco", Category.POUCH),
    # BAT-owned Swedish snus manufacturer.
    "skruf snus": ("British American Tobacco", Category.SNUS),
}

# Independent nicotine retailers/manufacturers, verified by name specificity.
# "snus" is a safe token: it is a Swedish tobacco product and the word has no
# unrelated meaning in any of the languages in our corpus.
KNOWN_NICOTINE = {
    "snusbolaget", "another snus factory", "snuspouch", "snushus",
    "snus vikings", "global snus", "snus fusion", "slavic snus",
    "the snus life", "juicysnus", "snusbros", "snuslab", "snusfrei",
    "royal nicotine", "athletic nicotine", "snusljus", "jet snus",
    "reykjavik snusverksmidja", "masnusqvta", "snusau",
}


# ---------------------------------------------------------------------------
# Tier C: hard exclusions. Tokens that look like nicotine terms but are not.
# ---------------------------------------------------------------------------

# Swedish "vapen" = weapons. Norwegian/Danish "vaben"/"vapen" likewise.
# French "vapeur" = steam. Italian "vapore" = steam.
FALSE_FRIEND_PATTERNS = [
    r"\bvapen\b",          # SE weapons
    r"vapenprodukter",
    r"vapeur",             # FR steam
    r"vapore",             # IT steam
    r"\bvapo(?:risateur)", # FR vaporiser (industrial)
]

# Advertisers manually confirmed as unrelated to nicotine. Each entry records
# what the business actually is, so the exclusion is auditable rather than a
# bare denylist.
CONFIRMED_NOT_NICOTINE = {
    "philip morris & son": "British countrywear retailer, Hereford. No relation to PMI.",
    "innovapet gmbh": "Pet supplies (DE). Substring 'vape' in 'innoVAPEt'.",
    "akvapet24, s.r.o.": "Pet and aquarium supplies (SK).",
    "novapeak e-commerce": "Home and garden (NL).",
    "novapetal nyc llc": "Gifts and florals (US).",
    "novapera pazarlama ve dis ticaret anonim sirketi": "Apparel/cosmetics (TR).",
    "yuvapen pvc kapi pencere isi sistemleri ins. taah. t": "PVC windows (TR).",
    "relevaperdite.com srl": "Leak detection services (IT).",
    "sas carvapeur974": "Car steam-cleaning, Reunion. 'vapeur' = steam.",
    "vapeur 2000": "Steam cleaning (FR).",
    "vapeur auto net": "Car steam-cleaning (FR).",
    "citev compagnie internationale des trains express a": "Heritage steam railway (FR).",
    "kjells vapen ab": "Firearms retailer (SE). 'vapen' = weapons.",
    "vapenprodukter sverige ab": "Firearms/weapons products (SE).",
    "jp vapen ab": "Firearms retailer (SE).",
    "advelo marketing solutions ou": "Marketing agency (EE). Matched 'velo marketing'.",
}


# ---------------------------------------------------------------------------
# Tier B: product-category signals, applied only after exclusions.
# Word-boundary matching, never bare substring.
# ---------------------------------------------------------------------------

CATEGORY_PATTERNS: list[tuple[Category, list[str]]] = [
    (Category.SNUS, [r"\bsnus\b", r"\bsnuff\b", r"\bportionssnus\b"]),
    (Category.POUCH, [r"\bnicotine\s+pouch", r"\bnikotinbeutel\b", r"\bnicopod",
                      r"\bvelo\b", r"\bzyn\b", r"\bnordic\s+spirit\b"]),
    (Category.VAPE, [r"\bvape\b", r"\bvapes\b", r"\bvaping\b", r"\bvaper\b",
                     r"\be-?cig", r"\bpuff\b", r"\belf\s?bar\b", r"\blost\s+mary\b",
                     r"\bvapeshop\b", r"\bvape\s?shop\b"]),
    (Category.HEATED, [r"\biqos\b", r"\bglo\b", r"\bheated\s+tobacco\b", r"\bheets\b"]),
    (Category.COMBUSTIBLE, [r"\bcigar\b", r"\bcigars\b", r"\bcigarette", r"\btobacco\b",
                            r"\btabak\b", r"\btabac\b"]),
]

# Google ad topics that corroborate a nicotine business. Used as supporting
# evidence only -- topics are multi-valued and noisy, so they can raise
# confidence but never establish it alone.
CORROBORATING_TOPICS = {"Food, Beverages & Tobacco"}


def normalize(name: str) -> str:
    """Lowercase, strip accents, collapse whitespace."""
    if not name:
        return ""
    n = unicodedata.normalize("NFKD", name)
    n = "".join(c for c in n if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", n.lower()).strip()


@dataclass
class Verdict:
    advertiser: str
    category: Category
    confidence: Confidence
    parent: str | None
    reason: str


def classify(advertiser: str, topics: str = "") -> Verdict:
    n = normalize(advertiser)
    if not n:
        return Verdict(advertiser, Category.UNKNOWN, Confidence.QUARANTINE, None,
                       "empty advertiser name")

    # 1. Manually confirmed non-nicotine businesses.
    if n in CONFIRMED_NOT_NICOTINE:
        return Verdict(advertiser, Category.NOT_NICOTINE, Confidence.VERIFIED, None,
                       CONFIRMED_NOT_NICOTINE[n])

    # 2. Known Big Tobacco entities. Checked before false-friends because
    #    "British American Tobacco" must never be filtered out by accident.
    for key, (parent, cat) in BIG_TOBACCO.items():
        if key in n:
            return Verdict(advertiser, cat, Confidence.VERIFIED, parent,
                           f"registered entity matches known corporate group '{parent}'")

    # 3. False friends -- words that look like nicotine terms but are not.
    for pat in FALSE_FRIEND_PATTERNS:
        if re.search(pat, n):
            return Verdict(
                advertiser, Category.NOT_NICOTINE, Confidence.LIKELY, None,
                f"matches false-friend pattern /{pat}/ "
                "(e.g. Swedish 'vapen'=weapons, French 'vapeur'=steam); "
                "needs manual confirmation before exclusion is final")

    # 4. Known independent nicotine businesses.
    for key in KNOWN_NICOTINE:
        if key in n:
            cat = Category.SNUS if "snus" in key else Category.POUCH
            return Verdict(advertiser, cat, Confidence.VERIFIED, None,
                           f"known nicotine retailer (matched '{key}')")

    # 5. Word-boundary category signals.
    hits: list[Category] = []
    for cat, pats in CATEGORY_PATTERNS:
        if any(re.search(p, n) for p in pats):
            hits.append(cat)

    if not hits:
        return Verdict(advertiser, Category.UNKNOWN, Confidence.QUARANTINE, None,
                       "no category signal in advertiser name")

    topic_set = {t.strip() for t in (topics or "").split(",")}
    corroborated = bool(topic_set & CORROBORATING_TOPICS)
    cat = hits[0] if len(hits) == 1 else Category.MIXED

    if corroborated:
        return Verdict(advertiser, cat, Confidence.LIKELY, None,
                       f"name signal ({cat.value}) corroborated by Google topic "
                       "'Food, Beverages & Tobacco'")
    return Verdict(advertiser, cat, Confidence.QUARANTINE, None,
                   f"name signal ({cat.value}) but no corroborating topic; "
                   "requires manual verification of the advertiser's actual business")


SCHEMA = """
CREATE TABLE IF NOT EXISTS advertiser_class (
    advertiser   TEXT PRIMARY KEY,
    category     TEXT NOT NULL,
    confidence   TEXT NOT NULL,
    parent       TEXT,
    reason       TEXT,
    n_creatives  INTEGER,
    hq           TEXT,
    reviewed_by  TEXT,
    reviewed_at  TEXT
);
"""


def classify_corpus(db: Path = DB_PATH) -> dict:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    rows = conn.execute(
        "SELECT advertiser, advertiser_hq AS hq, COUNT(*) n, "
        "GROUP_CONCAT(DISTINCT topic) topics "
        "FROM google_ads GROUP BY advertiser"
    ).fetchall()

    counts: dict[str, int] = {}
    creative_counts: dict[str, int] = {}
    for r in rows:
        v = classify(r["advertiser"], r["topics"] or "")
        conn.execute(
            "INSERT OR REPLACE INTO advertiser_class "
            "(advertiser, category, confidence, parent, reason, n_creatives, hq) "
            "VALUES (?,?,?,?,?,?,?)",
            (r["advertiser"], v.category.value, v.confidence.value, v.parent,
             v.reason, r["n"], r["hq"]),
        )
        key = f"{v.category.value}/{v.confidence.value}"
        counts[key] = counts.get(key, 0) + 1
        creative_counts[key] = creative_counts.get(key, 0) + r["n"]
    conn.commit()
    conn.close()
    return {"advertisers": counts, "creatives": creative_counts}


if __name__ == "__main__":
    stats = classify_corpus()
    print("advertisers by category/confidence:")
    for k in sorted(stats["advertisers"]):
        print(f"  {k:<42} {stats['advertisers'][k]:>4} advertisers  "
              f"{stats['creatives'][k]:>5} creatives")
