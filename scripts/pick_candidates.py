#!/usr/bin/env python3
"""Pick top-N enrichment candidates: VN persons with a Vietnamese Wikipedia
article, born 1850-2010, currently missing bio_short in our DB.

SPARQL gives us (qid, vi-wiki-title) pairs. Then we filter against the
existing DB to skip persons already enriched.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "wikipath.duckdb"
USER_AGENT = "wikipath-cand/0.1 (https://github.com/piazlabs/wikipath; sonpiaz@gmail.com)"
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

# Persons with a vi.wikipedia article + born in given year band.
#
# Pool definition (post-2026-05-10 expansion, see SPEC §4.7):
#   - Must be a human (P31 = Q5)
#   - Must have a Vietnamese Wikipedia article (we need it to enrich from)
#   - Must have a birth date in the given year band
#   - Either Vietnamese citizenship (P27 = Q881)
#     OR Vietnamese ethnicity (P172 = Q126480)  [captures diaspora]
#   - Ranked by sitelinks count (better fame proxy than has-image since many
#     historic VN scholars have vi-wiki but no P18); has-image is a tiebreaker.
#
# Year band default 1200-2010 (was 1850-2010). Wider band covers pre-modern
# scholars: Nguyễn Trãi (1380), Lê Quý Đôn (1726), Chu Văn An (1292), etc.
QUERY = """
SELECT DISTINCT ?p ?pLabel ?title ?birth ?image ?sitelinks
WHERE {
  {
    ?p wdt:P31 wd:Q5 ;
       wdt:P27 wd:Q881 .
  } UNION {
    ?p wdt:P31 wd:Q5 ;
       wdt:P172 wd:Q126480 .
  }
  ?p wdt:P569 ?birth .
  FILTER(YEAR(?birth) >= %d && YEAR(?birth) <= %d)
  ?article schema:about ?p ;
           schema:inLanguage "vi" ;
           schema:isPartOf <https://vi.wikipedia.org/> ;
           schema:name ?title .
  ?p wikibase:sitelinks ?sitelinks .
  OPTIONAL { ?p wdt:P18 ?image }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "vi,en" }
}
ORDER BY DESC(?sitelinks) DESC(?image) ?birth
LIMIT %d
"""


def sparql(query: str) -> dict:
    body = urllib.parse.urlencode({"query": query, "format": "json"}).encode()
    req = urllib.request.Request(
        SPARQL_ENDPOINT, data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)


def value_qid(b: dict, k: str) -> str | None:
    v = b.get(k)
    if not v:
        return None
    m = re.search(r"/(Q\d+)$", v["value"])
    return m.group(1) if m else None


def value_lit(b: dict, k: str) -> str | None:
    v = b.get(k)
    return v["value"] if v else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("-n", "--limit", type=int, default=200)
    ap.add_argument("--year-from", type=int, default=1200)
    ap.add_argument("--year-to", type=int, default=2010)
    ap.add_argument("--skip-first", type=int, default=0,
                    help="skip the top N candidates (use for batch slicing)")
    ap.add_argument("--min-statements", type=int, default=20,
                    help="min Wikidata statements (signal for fame)")
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--include-with-bio", action="store_true",
                    help="don't skip persons that already have bio_short")
    args = ap.parse_args()

    # Over-fetch a buffer beyond args.limit to compensate for the DB skip
    # filter (already-enriched persons). Cap at 10000 — Wikidata default
    # endpoint limit.
    fetch_n = min(10000, args.limit + 800)
    q = QUERY % (args.year_from, args.year_to, fetch_n)
    _ = args.min_statements
    print(f"sparql: years {args.year_from}-{args.year_to}, top {fetch_n} "
          f"(ranked by has-image then birth)…", file=sys.stderr)
    data = sparql(q)
    bindings = data.get("results", {}).get("bindings", [])
    print(f"sparql returned {len(bindings)} candidates", file=sys.stderr)

    con = duckdb.connect(str(args.db), read_only=True)
    skip_qids = set()
    if not args.include_with_bio:
        rows = con.execute(
            "SELECT wikidata_qid FROM person "
            "WHERE wikidata_qid IS NOT NULL AND bio_short IS NOT NULL AND bio_short != ''"
        ).fetchall()
        skip_qids = {r[0] for r in rows}
        print(f"skipping {len(skip_qids)} qids already with bio", file=sys.stderr)

    candidates = []
    skipped_first = 0
    for b in bindings:
        qid = value_qid(b, "p")
        if not qid:
            continue
        if qid in skip_qids:
            continue
        title = value_lit(b, "title")
        label = value_lit(b, "pLabel")
        if not title:
            continue
        # Skip rows where label = qid (no human-readable label)
        if label and label.startswith("Q") and label[1:].isdigit():
            continue
        # Slice: skip leading N candidates so we can paginate by batch
        if skipped_first < args.skip_first:
            skipped_first += 1
            continue
        has_image = bool(b.get("image"))
        sitelinks_raw = value_lit(b, "sitelinks")
        sitelinks = int(sitelinks_raw) if sitelinks_raw and sitelinks_raw.isdigit() else 0
        candidates.append({
            "qid": qid,
            "title": title,
            "label": label or title,
            "has_image": has_image,
            "sitelinks": sitelinks,
        })
        if len(candidates) >= args.limit:
            break

    print(f"selected {len(candidates)} candidates after DB filter",
          file=sys.stderr)
    args.out.write_text(json.dumps(candidates, ensure_ascii=False, indent=2))
    print(f"wrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
