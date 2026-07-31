"""
Verify quarantined advertisers by asking a fast model what each business is.

The classifier deliberately quarantines any advertiser it cannot positively
identify. This script resolves that queue by batching the names through
`cursor-agent` (Grok 4.5 Fast) and recording the verdict.

The model's answer is treated as evidence, not truth. Anything it marks
NICOTINE is promoted only to `likely` -- never to `verified` -- because a
model asserting that a company sells vapes is not the same as a filing-grade
fact. Verdicts feed a human-reviewable table with the reason attached.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import re
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ads.db"
MODEL = "cursor-grok-4.5-high-fast"
BATCH = 12

PROMPT_HEAD = """Answer with ONLY the requested lines. No preamble, no explanation, no tool use.

For each company below, output exactly one line in this format:
NAME|VERDICT|description

VERDICT must be one of:
  NICOTINE      - the company sells or markets tobacco, nicotine, vapes, snus, or nicotine pouches
  NOT_NICOTINE  - the company is in an unrelated business
  UNSURE        - you genuinely cannot determine what it does

Beware false friends: Swedish "vapen" means WEAPONS, French/Italian "vapeur"/"vapore" mean STEAM.
Some names merely contain the letters "vape" or "velo" by accident.
The description must be at most eight words and state the ACTUAL business.

Companies:
"""


def ask(names: list[str]) -> list[tuple[str, str, str]]:
    prompt = PROMPT_HEAD + "\n".join(names)
    proc = subprocess.run(
        ["cursor-agent", "-p", "--model", MODEL, "--force", prompt],
        capture_output=True, text=True, timeout=600,
    )
    out = proc.stdout.strip()
    results = []
    for line in out.splitlines():
        line = line.strip()
        if line.count("|") < 2:
            continue
        name, verdict, desc = [p.strip() for p in line.split("|", 2)]
        verdict = re.sub(r"[^A-Z_]", "", verdict.upper())
        if verdict not in {"NICOTINE", "NOT_NICOTINE", "UNSURE"}:
            continue
        results.append((name, verdict, desc))
    return results


def load_queue(conn: sqlite3.Connection) -> list[tuple[str, str, int]]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT advertiser, hq, n_creatives FROM advertiser_class "
        "WHERE confidence = 'quarantine' ORDER BY n_creatives DESC"
    ).fetchall()
    return [(r["advertiser"], r["hq"] or "", r["n_creatives"]) for r in rows]


def match_back(answer_name: str, queue: list[str]) -> str | None:
    """The model may lightly reformat names; match on a normalised prefix."""
    a = re.sub(r"[^a-z0-9]", "", answer_name.lower())
    if not a:
        return None
    best, best_len = None, 0
    for q in queue:
        b = re.sub(r"[^a-z0-9]", "", q.lower())
        if a.startswith(b[:18]) or b.startswith(a[:18]):
            if len(b) > best_len:
                best, best_len = q, len(b)
    return best


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    conn = sqlite3.connect(DB_PATH)
    queue = load_queue(conn)
    if not queue:
        print("nothing quarantined")
        return
    names = [f"{n} ({hq})" for n, hq, _ in queue]
    raw_names = [n for n, _, _ in queue]
    print(f"verifying {len(queue)} advertisers in batches of {BATCH}")

    batches = [names[i:i + BATCH] for i in range(0, len(names), BATCH)]
    answers: list[tuple[str, str, str]] = []
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for res in ex.map(ask, batches):
            answers.extend(res)
    print(f"  got {len(answers)} verdicts")

    now = datetime.now(timezone.utc).isoformat()
    applied = 0
    for answer_name, verdict, desc in answers:
        target = match_back(answer_name, raw_names)
        if not target:
            continue
        if verdict == "NICOTINE":
            conf, cat_sql = "likely", None
        elif verdict == "NOT_NICOTINE":
            conf, cat_sql = "verified", "not_nicotine"
        else:
            conf, cat_sql = "quarantine", None

        if cat_sql:
            conn.execute(
                "UPDATE advertiser_class SET category=?, confidence=?, reason=?, "
                "reviewed_by=?, reviewed_at=? WHERE advertiser=?",
                (cat_sql, conf, f"model verification: {desc}", MODEL, now, target),
            )
        else:
            conn.execute(
                "UPDATE advertiser_class SET confidence=?, reason=?, "
                "reviewed_by=?, reviewed_at=? WHERE advertiser=?",
                (conf, f"model verification: {desc}", MODEL, now, target),
            )
        applied += 1
    conn.commit()

    print(f"  applied {applied} verdicts")
    for row in conn.execute(
        "SELECT category, confidence, COUNT(*), SUM(n_creatives) "
        "FROM advertiser_class GROUP BY 1,2 ORDER BY 1,2"
    ):
        print(f"  {row[0]:<22} {row[1]:<11} {row[2]:>4} advertisers {row[3]:>5} creatives")
    conn.close()


if __name__ == "__main__":
    main()
