#!/usr/bin/env python3
"""Pick enrichment candidates from the existing DB (not SPARQL).

Where pick_candidates.py discovers *new* persons to import + enrich,
this script picks records *already in the DB* that need bio_short filled
in. Used for the doubling pilot protocol — small, controllable batches.

Filters (all must hold):
  - wikipedia_vi_url IS NOT NULL  (LLM needs ground truth)
  - bio_short IS NULL or ''        (not enriched yet)
  - birth_name passes display validators (handled by CHECK constraint
    on insert; we re-verify here so picker is robust against legacy rows)
  - has at least one relation       (skip isolated — they don't improve
    path-finding or tree exploration)

Output: JSON list of {qid, label, title} ready for enrich_async.py.

Ordering: connected count DESC, then sitelinks (proxied by relation count
since we don't store sitelinks locally). High-connectivity persons sit on
more traversal paths, so enriching them is worth more per dollar.

Usage:
  python scripts/pick_db_candidates.py --limit 50 -o data/candidates_pilot.json
"""
from __future__ import annotations

import argparse
import json
import urllib.parse
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "wikipath.duckdb"


def wiki_title_from_url(url: str) -> str | None:
    """Extract the article title from a vi.wikipedia.org URL."""
    if not url:
        return None
    # Expected: https://vi.wikipedia.org/wiki/Hồ_Chí_Minh
    # Or:       https://vi.wikipedia.org/wiki/H%E1%BB%93_Ch%C3%AD_Minh
    marker = "/wiki/"
    idx = url.find(marker)
    if idx < 0:
        return None
    encoded = url[idx + len(marker) :]
    encoded = encoded.split("#", 1)[0].split("?", 1)[0]
    if not encoded:
        return None
    return urllib.parse.unquote(encoded).replace("_", " ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--limit", type=int, required=True)
    ap.add_argument("--offset", type=int, default=0, help="Skip N before taking limit (for sequential doubling batches)")
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument(
        "--allow-isolated",
        action="store_true",
        help="Include records with 0 relations (default: skip)",
    )
    args = ap.parse_args()

    con = duckdb.connect(str(args.db), read_only=True)
    rel_filter = (
        ""
        if args.allow_isolated
        else """AND EXISTS (
            SELECT 1 FROM relation r
            WHERE r.from_person_id = p.id OR r.to_person_id = p.id
        )"""
    )
    rows = con.execute(
        f"""
        SELECT
          p.wikidata_qid AS qid,
          p.birth_name   AS label,
          p.wikipedia_vi_url AS url,
          (
            SELECT count(*) FROM relation r
            WHERE r.from_person_id = p.id OR r.to_person_id = p.id
          ) AS rel_count
        FROM person p
        WHERE p.wikipedia_vi_url IS NOT NULL
          AND (p.bio_short IS NULL OR p.bio_short = '')
          AND p.birth_name IS NOT NULL
          AND length(p.birth_name) >= 2
          AND NOT regexp_matches(p.birth_name, '^Q?[0-9]+$')
          {rel_filter}
        ORDER BY rel_count DESC, p.birth_date_y ASC NULLS LAST
        LIMIT ? OFFSET ?
        """,
        [args.limit, args.offset],
    ).fetchall()
    con.close()

    candidates = []
    for qid, label, url, rel_count in rows:
        title = wiki_title_from_url(url)
        if not title:
            continue
        candidates.append({"qid": qid, "label": label, "title": title, "rel_count": rel_count})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(candidates, indent=2, ensure_ascii=False))
    print(f"Picked {len(candidates)} candidate(s) → {args.out}")
    print(f"Top 3 by rel_count: {[(c['label'], c['rel_count']) for c in candidates[:3]]}")


if __name__ == "__main__":
    main()
