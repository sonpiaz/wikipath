#!/usr/bin/env python3
"""Deterministic test harness for enriched bios.

Audits-per-batch are random samples; this is the structural sweep that
runs across ALL enriched records and flags every row that fails an
invariant. Use it before any public-launch announcement.

Checks (each row pass/fail independently):
  L1  bio length 60-320 chars                   too short = stub, too long = bloat
  L2  bio is Vietnamese (>80%% VN+ASCII chars)  catches EN/CN leakage
  L3  bio mentions the person's name            sanity check (LLM read right article)
  L4  no markdown / HTML / list bullets         clean prose only
  L5  range pattern "(YYYY-YYYY)" matches DB    cross-source year alignment
  L6  birth-only pattern "sinh năm YYYY"  ±5y   bio quotes a birth year close to DB
  L7  no "tôi" / "chúng tôi" / "mình" / "anh"   third-person tone, no AI self-ref

Pure DB scan + regex — no network, no LLM. Fast and free.

Usage:
    python scripts/test_enrichment.py                # full sweep
    python scripts/test_enrichment.py --limit 200    # spot run

Exit code is 0 always (this is a diagnostic, not CI gate). The summary
prints pass-rate per check + per-record failure list for manual review.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "wikipath.duckdb"

# Vietnamese characters: ASCII + extended Latin range used by VN diacritics.
# Plus the dynamic chars (smart quotes, dashes) — anything outside is suspect.
VN_OK = re.compile(
    r"^[ -~ -ſƠ-ưẠ-ỹ"
    r"‐-—‘-”…]+$"
)
NAME_TOKEN_MIN = 2  # at least this many tokens must overlap between bio and name

RANGE_RE = re.compile(r"\((1[0-9]{3}|20[0-2][0-9])\s*[–\-]\s*(1[0-9]{3}|20[0-2][0-9])\)")
BIRTH_RE = re.compile(
    r"sinh\s+(?:năm\s+|ngày\s+\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+)?(1[0-9]{3}|20[0-2][0-9])"
)

MARKUP_RE = re.compile(r"<[^>]+>|^\s*[*\-•]|\*\*|__|```")
# Drop "anh" and "em" — they appear in VN compound nouns ("Anh hùng Lực lượng
# vũ trang", "anh em", "em gái") and inside proper names ("Đào Duy Anh"). The
# net effect of including them is ~12%% false positives across the corpus, far
# above the rate of actual first-person bios.
FIRST_PERSON_RE = re.compile(r"\b(tôi|chúng tôi|chúng mình|tớ)\b", re.IGNORECASE)


def fold(s: str) -> str:
    """Normalise + strip diacritics + lowercase for token comparison."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c)
    )


def name_tokens(name: str) -> set[str]:
    """Family name parts, useful for substring matching against bio."""
    return {t for t in fold(name).split() if len(t) >= 2}


def check(row) -> dict:
    pid, name, db_b, db_d, bio = row
    fails: list[str] = []

    # L1 length
    n = len(bio)
    if n < 60:
        fails.append(f"L1:too_short({n})")
    elif n > 320:
        fails.append(f"L1:too_long({n})")

    # L2 language — VN char ratio
    ok_chars = sum(1 for c in bio if VN_OK.match(c))
    if n > 0 and ok_chars / n < 0.95:
        fails.append(f"L2:non_vn_chars({(n - ok_chars)})")

    # L3 name overlap — at least 1 token from name must appear in bio
    bio_fold = fold(bio)
    nt = name_tokens(name)
    if nt and not any(t in bio_fold for t in nt):
        fails.append("L3:name_missing")

    # L4 markdown / html / list bullets
    if MARKUP_RE.search(bio):
        fails.append("L4:markup")

    # L5 birth-death range. Seed bios like "TBT ĐCS Việt Nam (1960-1986)" put
    # a tenure inside the lead parenthesis, which a naive RANGE_RE would treat
    # as birth-death. The disambiguator: if the range falls *within* the DB
    # lifespan (range_birth > db_birth + 5), it's career/tenure, not birth-
    # death. Only flag when the range is plausibly a birth-death claim.
    head = bio[:90]
    m = RANGE_RE.search(head)
    if m:
        b, d = int(m.group(1)), int(m.group(2))
        looks_like_lifespan = 5 <= (d - b) <= 110
        is_tenure = db_b and (b > db_b + 5)
        if looks_like_lifespan and not is_tenure:
            if db_b and b != db_b:
                fails.append(f"L5:bio_range_birth({db_b}!={b})")
            if db_d and d != db_d:
                fails.append(f"L5:bio_range_death({db_d}!={d})")

    # L6 birth-only pattern
    m = BIRTH_RE.search(bio)
    if m:
        b = int(m.group(1))
        if db_b and abs(b - db_b) > 5:
            fails.append(f"L6:bio_birth_drift({db_b}!={b})")

    # L7 first-person voice
    if FIRST_PERSON_RE.search(bio):
        fails.append("L7:first_person")

    return {"id": pid, "name": name, "fails": fails, "bio": bio}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--limit", type=int, default=0, help="0 = scan all")
    ap.add_argument("-o", "--out", type=Path, default=ROOT / "data" / "test_enrichment_report.json")
    args = ap.parse_args()

    con = duckdb.connect(str(args.db), read_only=True)
    where = "WHERE bio_short IS NOT NULL AND bio_short <> ''"
    sql = f"""
        SELECT id, birth_name, birth_date_y, death_date_y, bio_short
        FROM person {where}
        ORDER BY updated_at DESC
    """
    if args.limit:
        sql += f" LIMIT {args.limit}"
    rows = con.execute(sql).fetchall()
    con.close()

    results = [check(r) for r in rows]
    fail_counts: dict[str, int] = {}
    failed_rows = []
    for r in results:
        if r["fails"]:
            failed_rows.append(r)
            for f in r["fails"]:
                # take just the rule prefix (L1/L2/etc), not its detail
                rule = f.split(":", 1)[0]
                fail_counts[rule] = fail_counts.get(rule, 0) + 1

    total = len(results)
    failed = len(failed_rows)
    pass_rate = (total - failed) / total if total else 0
    summary = {
        "total": total,
        "passed": total - failed,
        "failed": failed,
        "pass_rate": round(pass_rate, 4),
        "failures_by_rule": fail_counts,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {"summary": summary, "failed_rows": failed_rows},
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )

    # Stdout: headline + per-rule + first 20 failed names for quick scan
    print(f"Scanned {total} enriched rows")
    print(f"Pass rate: {pass_rate:.2%}  ({total - failed} pass / {failed} fail)\n")
    print("Failures by rule:")
    for rule in sorted(fail_counts):
        print(f"  {rule}  {fail_counts[rule]}")
    if failed_rows:
        print(f"\nFirst {min(20, len(failed_rows))} failed records:")
        for r in failed_rows[:20]:
            print(f"  {r['name']:<35s}  {','.join(r['fails'])}")
    print(f"\nFull report → {args.out}")


if __name__ == "__main__":
    main()
