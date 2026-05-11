#!/usr/bin/env python3
"""Image enrichment — populate `person.avatar_url` from Wikidata P18.

SPARQL batched (`VALUES ?p { wd:Q1 wd:Q2 ... }`) in chunks of `--chunk-size`
QIDs per request. Each P18 value is a Wikimedia Commons filename; the URL
served via Commons Special:FilePath supports a `width` query parameter for
on-the-fly resize. We don't store the resized URL — just the canonical form
— and let `next/image` request the right width at render time.

Idempotent: only writes to persons where `avatar_url IS NULL` unless
`--overwrite` is passed.

Expected coverage on current 5,636-QID pool: 50-60% (~3,000-3,400 hits).
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
from typing import Iterable

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "wikipath.duckdb"
USER_AGENT = "wikipath-images/0.1 (https://github.com/piazlabs/wikipath; sonpiaz@gmail.com)"
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

# Special:FilePath template. Wikimedia auto-redirects to actual file URL,
# honoring the width parameter for thumbnail generation.
COMMONS_URL_TMPL = (
    "https://commons.wikimedia.org/wiki/Special:FilePath/{filename}?width=300"
)


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


def build_query(qids: list[str]) -> str:
    values = " ".join(f"wd:{q}" for q in qids)
    return f"""
SELECT ?p ?image WHERE {{
  VALUES ?p {{ {values} }}
  ?p wdt:P18 ?image .
}}
"""


def filename_from_uri(uri: str) -> str | None:
    """Extract the encoded filename from a Wikidata image URI.

    Example: http://commons.wikimedia.org/wiki/Special:FilePath/Foo.jpg
    → "Foo.jpg" (already URL-encoded by Wikidata).
    """
    m = re.search(r"FilePath/(.+)$", uri)
    return m.group(1) if m else None


def chunked(seq: list, n: int) -> Iterable[list]:
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--chunk-size", type=int, default=400,
                    help="QIDs per SPARQL request (Wikidata default cap ~500)")
    ap.add_argument("--overwrite", action="store_true",
                    help="overwrite existing avatar_url values")
    ap.add_argument("--sleep", type=float, default=0.5,
                    help="seconds between SPARQL chunks (be a good citizen)")
    args = ap.parse_args()

    con = duckdb.connect(str(args.db))

    where_avatar = "" if args.overwrite else " AND (avatar_url IS NULL OR avatar_url = '')"
    rows = con.execute(
        f"SELECT id, wikidata_qid FROM person "
        f"WHERE wikidata_qid IS NOT NULL{where_avatar}"
    ).fetchall()

    qid_to_id = {qid: pid for pid, qid in rows}
    qids = list(qid_to_id.keys())
    print(f"persons with QID needing image: {len(qids)}", file=sys.stderr)
    if not qids:
        return

    total_hits = 0
    chunks = list(chunked(qids, args.chunk_size))
    t0 = time.time()
    for i, chunk in enumerate(chunks, 1):
        try:
            data = sparql(build_query(chunk))
        except Exception as exc:
            print(f"  chunk {i}/{len(chunks)} FAILED: {exc}", file=sys.stderr)
            time.sleep(args.sleep * 2)
            continue

        bindings = data.get("results", {}).get("bindings", [])
        chunk_hits = 0
        for b in bindings:
            p_uri = b.get("p", {}).get("value", "")
            img_uri = b.get("image", {}).get("value", "")
            qid_match = re.search(r"/(Q\d+)$", p_uri)
            if not qid_match:
                continue
            qid = qid_match.group(1)
            fname = filename_from_uri(img_uri)
            if not fname:
                continue
            url = COMMONS_URL_TMPL.format(filename=fname)
            pid = qid_to_id.get(qid)
            if pid:
                con.execute(
                    "UPDATE person SET avatar_url = ?, "
                    "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    [url, pid],
                )
                chunk_hits += 1
        total_hits += chunk_hits
        elapsed = time.time() - t0
        rate = total_hits / max(1, elapsed)
        print(f"  chunk {i}/{len(chunks)}: +{chunk_hits} hits "
              f"(running total {total_hits}, {rate:.1f}/s)", file=sys.stderr)
        time.sleep(args.sleep)

    con.execute("CHECKPOINT")
    print(f"\nDONE: matched {total_hits}/{len(qids)} "
          f"({total_hits * 100 / max(1, len(qids)):.1f}% coverage) "
          f"in {time.time() - t0:.1f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
