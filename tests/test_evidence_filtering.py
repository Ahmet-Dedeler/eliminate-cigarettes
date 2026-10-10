"""Evidence packets must never include false positives or unverified advertisers."""
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import classify  # noqa: E402
import evidence  # noqa: E402
import google_harvest  # noqa: E402

ADVERTISERS = [
    ("British American Tobacco Sweden AB", "Food, Beverages & Tobacco"),  # verified
    ("Snusbolaget Norden AB", "Food, Beverages & Tobacco"),               # verified
    ("Kjells Vapen AB", "Shopping"),                # weapons shop: must be excluded
    ("Innovapet GmbH", "Pets & Animals"),           # pet supplies: must be excluded
    ("Philip Morris & Son", "Apparel"),             # countrywear: must be excluded
    ("Some Vape Shop Ltd", ""),                     # no corroboration: quarantined
    ("Mystery Vapes LLC", "Food, Beverages & Tobacco"),  # likely, not verified
]


def make_db() -> sqlite3.Connection:
    path = Path(tempfile.mkdtemp()) / "ads.db"
    conn = sqlite3.connect(path)
    conn.executescript(google_harvest.SCHEMA)
    for i, (name, topic) in enumerate(ADVERTISERS):
        conn.execute(
            "INSERT INTO google_ads (creative_id, advertiser, advertiser_legal, "
            "advertiser_hq, verification, creative_url, topic, regions, n_regions, "
            "last_shown) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (f"CR{i}", name, name, "SE", "VERIFIED",
             f"https://adstransparency.google.com/creative/CR{i}", topic,
             "SE,DE", 2, "2026-07-30"),
        )
    conn.commit()
    classify.classify_corpus(path)
    conn = sqlite3.connect(path)
    # Simulate an advertiser promoted to 'likely' (e.g. by verify_advertisers.py)
    conn.execute(
        "UPDATE advertiser_class SET confidence='likely' "
        "WHERE advertiser='Mystery Vapes LLC'"
    )
    conn.commit()
    return conn


def test_report_excludes_false_positives_and_unverified():
    conn = make_db()
    report = evidence.build_report(conn)
    assert "British American Tobacco Sweden AB" in report
    assert "Snusbolaget Norden AB" in report
    for bad in ["Kjells Vapen", "Innovapet", "Philip Morris & Son",
                "Some Vape Shop", "Mystery Vapes"]:
        assert f"### {bad}" not in report, bad


def test_include_likely_adds_likely_but_never_false_positives():
    conn = make_db()
    report = evidence.build_report(conn, include_likely=True)
    assert "### Mystery Vapes LLC" in report
    assert "### Kjells Vapen AB" not in report
    assert "### Some Vape Shop Ltd" not in report  # quarantine never published


if __name__ == "__main__":
    test_report_excludes_false_positives_and_unverified()
    test_include_likely_adds_likely_but_never_false_positives()
    print("ok")