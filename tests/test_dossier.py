"""HTML/PDF dossiers: content, escaping, screenshots, PDF rendering."""
import base64
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import classify  # noqa: E402
import evidence  # noqa: E402
import google_harvest  # noqa: E402

# 1x1 transparent PNG
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def make_db(tmp: Path) -> sqlite3.Connection:
    path = tmp / "ads.db"
    conn = sqlite3.connect(path)
    conn.executescript(google_harvest.SCHEMA)
    rows = [
        ("CR1", "AR111", "British American Tobacco Sweden AB", "SE", "2026-07-30"),
        ("CR2", "AR111", "British American Tobacco Sweden AB", "SE", "2026-05-01"),
        ("CR3", "AR222", "Kjells Vapen AB", "SE", "2026-07-30"),  # false positive
    ]
    for cid, aid, name, hq, last in rows:
        conn.execute(
            "INSERT INTO google_ads (creative_id, advertiser_id, advertiser, "
            "advertiser_legal, advertiser_hq, verification, creative_url, ad_format, "
            "topic, regions, n_regions, first_shown, last_shown, harvested_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cid, aid, name, name, hq, "VERIFIED",
             f"https://adstransparency.google.com/advertiser/{aid}/creative/{cid}",
             "IMAGE", "Food, Beverages & Tobacco", "SE,DE", 2, "2026-01-01", last,
             "2026-07-31T00:00:00+00:00"),
        )
    conn.commit()
    classify.classify_corpus(path)
    return sqlite3.connect(path)


def test_html_dossier_content_and_screenshot():
    tmp = Path(tempfile.mkdtemp())
    shots = tmp / "shots"
    shots.mkdir()
    (shots / "CR1.png").write_bytes(PNG)
    conn = make_db(tmp)
    files = evidence.write_dossiers(conn, tmp / "out", "html", shot_dir=shots)
    names = [f.name for f in files]
    assert names == ["british-american-tobacco-sweden-ab.html"]  # no false positive
    doc = files[0].read_text()
    assert "AR111" in doc                                   # advertiser ID
    assert "Ads for tobacco or any products containing tobacco" in doc  # clause
    assert "data:image/png;base64," in doc                  # screenshot embedded
    assert "No local screenshot" in doc                     # CR2 has none
    assert "https://adstransparency.google.com/advertiser/AR111/creative/CR2" in doc


def test_untrusted_values_are_escaped():
    assert evidence.esc('<script>alert(1)</script>') == "&lt;script&gt;alert(1)&lt;/script&gt;"
    assert "<a" not in evidence.safe_link("javascript:alert(1)")


def test_path_traversal_in_creative_id_is_neutralised():
    tmp = Path(tempfile.mkdtemp())
    assert evidence.find_screenshot("../../etc/passwd", tmp) is None


def test_pdf_renders():
    try:
        import weasyprint  # noqa: F401
    except (ImportError, OSError):
        return  # not installed, or native libraries missing (e.g. Windows)
    tmp = Path(tempfile.mkdtemp())
    conn = make_db(tmp)
    files = evidence.write_dossiers(conn, tmp / "out", "pdf", shot_dir=tmp)
    assert files[0].read_bytes().startswith(b"%PDF")


def test_pdf_missing_native_libs_gives_clear_message():
    """WeasyPrint raising OSError (no GTK/Pango) must exit cleanly, not crash."""
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "weasyprint":
            raise OSError("cannot load library 'libgobject-2.0-0'")
        return real_import(name, *a, **k)

    builtins.__import__ = fake_import
    try:
        tmp = Path(tempfile.mkdtemp())
        conn = make_db(tmp)
        try:
            evidence.write_dossiers(conn, tmp / "out", "pdf", shot_dir=tmp)
        except SystemExit as exc:
            assert "--format html" in str(exc)
        else:
            raise AssertionError("expected SystemExit")
    finally:
        builtins.__import__ = real_import


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")