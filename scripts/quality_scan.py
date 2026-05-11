#!/usr/bin/env python3
"""Pre-enrichment data quality scan.

Runs read-only checks against `wikipath.duckdb` and emits two artifacts:

  data/quality_report.json   machine-readable counts + samples (for follow-up
                             scripts and CI / regression tracking).
  data/quality_report.md     human-readable summary Son reviews before bulk
                             enrichment.

Purpose: surface anything that would waste Kyma credit if we enriched on
top of it — duplicates, temporal anomalies, garbage names, isolated nodes,
records with no source ground truth — *before* spending money.

Read-only. Does NOT mutate the DB.

Usage:
    python scripts/quality_scan.py            # full scan
    python scripts/quality_scan.py --limit 5  # tighter sample size per category
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "wikipath.duckdb"
DATA_DIR = ROOT / "data"
JSON_OUT = DATA_DIR / "quality_report.json"
MD_OUT = DATA_DIR / "quality_report.md"

CURRENT_YEAR = datetime.now().year

# Display-side filter mirrors api package: hide Q-only and year-only fallback
# names. CHECK constraint catches these at insert now, but legacy rows can
# still exist.
GARBAGE_NAME_REGEX = r"^Q?[0-9]+$"

# When counting "people who must be dead" we use a generous cutoff so we don't
# flag living centenarians.
LIKELY_DEAD_CUTOFF_AGE = 110


def q(con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None):
    cur = con.execute(sql, params or [])
    cols = [d[0] for d in cur.description] if cur.description else []
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def scan(limit: int) -> dict[str, Any]:
    con = duckdb.connect(str(DB), read_only=True)

    out: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "db": str(DB),
        "sample_limit": limit,
        "totals": {},
        "checks": {},
    }

    # ── Totals ──────────────────────────────────────────────────────────
    totals = q(con, """
        SELECT
          (SELECT count(*) FROM person)                                   AS persons,
          (SELECT count(*) FROM person WHERE bio_short IS NOT NULL AND bio_short <> '') AS bio_filled,
          (SELECT count(*) FROM person WHERE avatar_url IS NOT NULL)      AS avatar_filled,
          (SELECT count(*) FROM person WHERE wikipedia_vi_url IS NOT NULL) AS has_wiki_vi,
          (SELECT count(*) FROM person WHERE wikidata_qid IS NOT NULL)    AS has_qid,
          (SELECT count(*) FROM relation)                                 AS relations
    """)[0]
    out["totals"] = totals

    # ── Check 1: Duplicate name + birth year (±2y) ──────────────────────
    # Same name + birth year within 2y on either side strongly suggests
    # double-entry. Exposes Wikidata + Wikipedia VN merge artefacts.
    dup_rows = q(con, f"""
        WITH n AS (
          SELECT id, wikidata_qid, birth_name, birth_date_y, death_date_y
          FROM person
          WHERE birth_name IS NOT NULL
            AND birth_date_y IS NOT NULL
        )
        SELECT a.id AS a_id, a.wikidata_qid AS a_qid,
               b.id AS b_id, b.wikidata_qid AS b_qid,
               a.birth_name AS name,
               a.birth_date_y AS a_birth, b.birth_date_y AS b_birth
        FROM n a
        JOIN n b ON a.birth_name = b.birth_name
                AND a.id < b.id
                AND abs(a.birth_date_y - b.birth_date_y) <= 2
        ORDER BY a.birth_name
        LIMIT {limit}
    """)
    dup_count = q(con, """
        SELECT count(*) AS c FROM (
          SELECT a.id, b.id
          FROM person a JOIN person b
            ON a.birth_name = b.birth_name
           AND a.id < b.id
           AND abs(a.birth_date_y - b.birth_date_y) <= 2
          WHERE a.birth_name IS NOT NULL AND a.birth_date_y IS NOT NULL
        )
    """)[0]["c"]
    out["checks"]["duplicate_pairs"] = {
        "count": dup_count,
        "description": "Same birth_name with birth year within ±2y. Likely double-entries from Wikidata vs Wikipedia VN import. Manual review before enrichment.",
        "samples": dup_rows,
    }

    # ── Check 2: Garbage names lingering in DB ──────────────────────────
    # CHECK constraint should block insert; legacy rows may exist.
    garbage = q(con, f"""
        SELECT id, wikidata_qid, birth_name, era, dynasty
        FROM person
        WHERE birth_name IS NOT NULL
          AND (
            regexp_matches(birth_name, '{GARBAGE_NAME_REGEX}')
            OR length(birth_name) < 2
          )
        LIMIT {limit}
    """)
    garbage_count = q(con, f"""
        SELECT count(*) AS c FROM person
        WHERE birth_name IS NOT NULL
          AND (regexp_matches(birth_name, '{GARBAGE_NAME_REGEX}') OR length(birth_name) < 2)
    """)[0]["c"]
    out["checks"]["garbage_names"] = {
        "count": garbage_count,
        "description": "Q-only ('Q12345'), year-only ('1949'), or too-short names. These are filtered at display time but still occupy enrichment slots.",
        "samples": garbage,
    }

    # ── Check 3: NULL birth_name + no Wikipedia link ────────────────────
    # No ground truth for LLM enrichment → high false-positive risk.
    nameless = q(con, f"""
        SELECT id, wikidata_qid, era, dynasty, birth_date_y
        FROM person
        WHERE birth_name IS NULL
          AND wikipedia_vi_url IS NULL
        LIMIT {limit}
    """)
    nameless_count = q(con, """
        SELECT count(*) AS c FROM person
        WHERE birth_name IS NULL AND wikipedia_vi_url IS NULL
    """)[0]["c"]
    out["checks"]["nameless_no_source"] = {
        "count": nameless_count,
        "description": "NULL birth_name AND no Wikipedia URL. LLM has nothing to ground on — DO NOT enrich these.",
        "samples": nameless,
    }

    # ── Check 4: Future dates ───────────────────────────────────────────
    future = q(con, f"""
        SELECT id, wikidata_qid, birth_name, birth_date_y, death_date_y
        FROM person
        WHERE birth_date_y > {CURRENT_YEAR}
           OR death_date_y > {CURRENT_YEAR}
        LIMIT {limit}
    """)
    future_count = q(con, f"""
        SELECT count(*) AS c FROM person
        WHERE birth_date_y > {CURRENT_YEAR} OR death_date_y > {CURRENT_YEAR}
    """)[0]["c"]
    out["checks"]["future_dates"] = {
        "count": future_count,
        "description": f"birth_date_y or death_date_y > {CURRENT_YEAR}. Always wrong.",
        "samples": future,
    }

    # ── Check 5: Parent-child age gap violation ─────────────────────────
    # Parent must be ≥12y older than child and ≤60y older. Outside that band
    # the relation is suspect.
    age_gap = q(con, f"""
        SELECT r.from_person_id AS child_id, r.to_person_id AS parent_id,
               c.birth_name AS child_name, p.birth_name AS parent_name,
               c.birth_date_y AS child_birth, p.birth_date_y AS parent_birth,
               c.birth_date_y - p.birth_date_y AS gap
        FROM relation r
        JOIN person c ON c.id = r.from_person_id
        JOIN person p ON p.id = r.to_person_id
        WHERE r.kind IN ('parent_father', 'parent_mother')
          AND c.birth_date_y IS NOT NULL
          AND p.birth_date_y IS NOT NULL
          AND (c.birth_date_y - p.birth_date_y < 12 OR c.birth_date_y - p.birth_date_y > 60)
        ORDER BY abs(c.birth_date_y - p.birth_date_y) DESC
        LIMIT {limit}
    """)
    age_gap_count = q(con, """
        SELECT count(*) AS c
        FROM relation r
        JOIN person c ON c.id = r.from_person_id
        JOIN person p ON p.id = r.to_person_id
        WHERE r.kind IN ('parent_father', 'parent_mother')
          AND c.birth_date_y IS NOT NULL AND p.birth_date_y IS NOT NULL
          AND (c.birth_date_y - p.birth_date_y < 12 OR c.birth_date_y - p.birth_date_y > 60)
    """)[0]["c"]
    out["checks"]["parent_child_age_gap"] = {
        "count": age_gap_count,
        "description": "Parent < 12y or > 60y older than child. Either wrong birth year or wrong relation.",
        "samples": age_gap,
    }

    # ── Check 6: Likely-dead but no death_year ──────────────────────────
    likely_dead = q(con, f"""
        SELECT id, wikidata_qid, birth_name, birth_date_y, era
        FROM person
        WHERE birth_date_y IS NOT NULL
          AND birth_date_y < {CURRENT_YEAR - LIKELY_DEAD_CUTOFF_AGE}
          AND death_date_y IS NULL
        LIMIT {limit}
    """)
    likely_dead_count = q(con, f"""
        SELECT count(*) AS c FROM person
        WHERE birth_date_y IS NOT NULL
          AND birth_date_y < {CURRENT_YEAR - LIKELY_DEAD_CUTOFF_AGE}
          AND death_date_y IS NULL
    """)[0]["c"]
    out["checks"]["likely_dead_no_death_year"] = {
        "count": likely_dead_count,
        "description": f"Born before {CURRENT_YEAR - LIKELY_DEAD_CUTOFF_AGE} but no death_date_y. Almost certainly missing data, not still alive.",
        "samples": likely_dead,
    }

    # ── Check 7: Isolated nodes (no relations either side) ──────────────
    isolated = q(con, f"""
        SELECT id, wikidata_qid, birth_name, era, dynasty
        FROM person p
        WHERE NOT EXISTS (SELECT 1 FROM relation r WHERE r.from_person_id = p.id OR r.to_person_id = p.id)
        LIMIT {limit}
    """)
    isolated_count = q(con, """
        SELECT count(*) AS c FROM person p
        WHERE NOT EXISTS (SELECT 1 FROM relation r WHERE r.from_person_id = p.id OR r.to_person_id = p.id)
    """)[0]["c"]
    out["checks"]["isolated_nodes"] = {
        "count": isolated_count,
        "description": "No relations on either side. Enriching adds bio but does NOT improve path-finding or tree exploration.",
        "samples": isolated,
    }

    # ── Check 8: Era / birth_year mismatch ──────────────────────────────
    # If era says one bucket but birth_year falls in another, era was set
    # without checking the year. Display will look wrong.
    era_mismatch = q(con, f"""
        SELECT id, wikidata_qid, birth_name, birth_date_y, era
        FROM person
        WHERE birth_date_y IS NOT NULL AND era IS NOT NULL
          AND (
            (era = 'pre-1500'     AND birth_date_y >= 1500) OR
            (era = '1500-1900'    AND (birth_date_y < 1500 OR birth_date_y >= 1900)) OR
            (era = '1900-1950'    AND (birth_date_y < 1900 OR birth_date_y >= 1950)) OR
            (era = '1950+'        AND birth_date_y < 1950)
          )
        LIMIT {limit}
    """)
    era_mismatch_count = q(con, """
        SELECT count(*) AS c FROM person
        WHERE birth_date_y IS NOT NULL AND era IS NOT NULL
          AND (
            (era = 'pre-1500'     AND birth_date_y >= 1500) OR
            (era = '1500-1900'    AND (birth_date_y < 1500 OR birth_date_y >= 1900)) OR
            (era = '1900-1950'    AND (birth_date_y < 1900 OR birth_date_y >= 1950)) OR
            (era = '1950+'        AND birth_date_y < 1950)
          )
    """)[0]["c"]
    out["checks"]["era_birth_mismatch"] = {
        "count": era_mismatch_count,
        "description": "Era bucket disagrees with birth_date_y. Cheap to repair, hurts display credibility.",
        "samples": era_mismatch,
    }

    # ── Check 9: Self-relations ─────────────────────────────────────────
    self_rel = q(con, f"""
        SELECT id, from_person_id, kind
        FROM relation
        WHERE from_person_id = to_person_id
        LIMIT {limit}
    """)
    self_rel_count = q(con, """
        SELECT count(*) AS c FROM relation WHERE from_person_id = to_person_id
    """)[0]["c"]
    out["checks"]["self_relations"] = {
        "count": self_rel_count,
        "description": "X is related to X. Always wrong.",
        "samples": self_rel,
    }

    # ── Check 10: Birth-year-only as name ('1949') leaking past CHECK ──
    # CHECK regex already blocks this pattern at insert. Verify nothing slipped
    # through prior to the CHECK being added.
    year_name = q(con, f"""
        SELECT id, wikidata_qid, birth_name
        FROM person
        WHERE birth_name IS NOT NULL
          AND regexp_matches(birth_name, '^[12][0-9]{{3}}$')
        LIMIT {limit}
    """)
    year_name_count = q(con, """
        SELECT count(*) AS c FROM person
        WHERE birth_name IS NOT NULL AND regexp_matches(birth_name, '^[12][0-9]{3}$')
    """)[0]["c"]
    out["checks"]["year_only_name"] = {
        "count": year_name_count,
        "description": "Name is a 4-digit year like '1949'. Subset of garbage_names but called out separately for tracking the year-import regression.",
        "samples": year_name,
    }

    con.close()
    return out


def to_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# wikipath data quality report")
    lines.append("")
    lines.append(f"Generated: {report['generated_at']}")
    lines.append(f"DB: `{report['db']}`")
    lines.append(f"Sample size per check: {report['sample_limit']}")
    lines.append("")
    t = report["totals"]
    lines.append("## Totals")
    lines.append("")
    lines.append(f"- Persons: **{t['persons']:,}**")
    lines.append(
        f"- bio_short filled: {t['bio_filled']:,} ({t['bio_filled'] / t['persons']:.1%})"
    )
    lines.append(
        f"- avatar_url filled: {t['avatar_filled']:,} ({t['avatar_filled'] / t['persons']:.1%})"
    )
    lines.append(
        f"- Wikipedia VN URL: {t['has_wiki_vi']:,} ({t['has_wiki_vi'] / t['persons']:.1%})"
    )
    lines.append(
        f"- Wikidata QID: {t['has_qid']:,} ({t['has_qid'] / t['persons']:.1%})"
    )
    lines.append(f"- Relations: {t['relations']:,}")
    lines.append("")
    lines.append("## Quality checks")
    lines.append("")
    for name, check in report["checks"].items():
        lines.append(f"### `{name}` — **{check['count']:,}** record(s)")
        lines.append("")
        lines.append(check["description"])
        lines.append("")
        if check["samples"]:
            lines.append("Samples:")
            lines.append("")
            lines.append("```")
            for s in check["samples"]:
                lines.append(json.dumps(s, default=str, ensure_ascii=False))
            lines.append("```")
            lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10, help="Sample rows per check")
    args = ap.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    report = scan(args.limit)
    JSON_OUT.write_text(json.dumps(report, indent=2, default=str, ensure_ascii=False))
    MD_OUT.write_text(to_markdown(report))
    print(f"Wrote {JSON_OUT}")
    print(f"Wrote {MD_OUT}")
    # Headline numbers to stdout
    print("\nHeadlines:")
    for name, check in report["checks"].items():
        print(f"  {name:<30s} {check['count']:>6,}")


if __name__ == "__main__":
    main()
