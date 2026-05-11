#!/usr/bin/env python3
"""Backfill cleanup — NULL out person.birth_name where the parser leaked
a bare year (e.g. "1936") or a Wikidata QID (e.g. "Q12345") instead of a
real name.

Forward-only fix lives in:
  - scripts/import_wiki_vi.py   (year-leak from infobox link extraction)
  - scripts/import_wikidata.py  (QID-leak from missing SPARQL ?toLabel)

This script is a one-shot patch for rows already in DB. It does NOT
delete relations or person rows — see scripts/cleanup_bad_llm_names.py
for the full delete pattern.

Side effect: relations pointing at these persons remain valid but now
hang off a NULL-named row. Re-running the relevant importer (or LLM
enrichment) can later backfill the real name via wikidata_qid /
wikipedia_vi_url.

Defaults to --dry-run. Pass --apply to commit changes.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "wikipath.duckdb"

# Same regex shapes used by the new validators in import_wiki_vi.py and
# import_wikidata.py — keep in sync if you tighten validation there.
BAD_NAME_PREDICATE = (
    "regexp_matches(birth_name, '^[0-9]+$') "
    "OR regexp_matches(birth_name, '^Q[0-9]+$') "
    "OR length(trim(birth_name)) < 2"
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--apply", action="store_true",
                    help="commit the NULL update (default: dry-run)")
    args = ap.parse_args()

    con = duckdb.connect(str(args.db), read_only=not args.apply)

    rows = con.execute(
        f"SELECT id, birth_name, primary_source FROM person "
        f"WHERE {BAD_NAME_PREDICATE} "
        f"ORDER BY primary_source, birth_name"
    ).fetchall()

    by_source: dict[str, int] = {}
    for _, _, src in rows:
        by_source[src or "<null>"] = by_source.get(src or "<null>", 0) + 1

    print(f"Found {len(rows)} rows with junk birth_name")
    for src, n in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"  {n:6d}  primary_source={src}")
    print()
    print("Sample (up to 10):")
    for pid, name, src in rows[:10]:
        print(f"  {str(pid)[:8]}…  birth_name={name!r}  source={src}")
    print()

    if not rows:
        print("Nothing to clean.")
        return

    if not args.apply:
        print("DRY RUN — pass --apply to commit.")
        return

    con.execute(
        f"UPDATE person "
        f"SET birth_name = NULL, updated_at = CURRENT_TIMESTAMP "
        f"WHERE {BAD_NAME_PREDICATE}"
    )
    con.execute("CHECKPOINT")
    print(f"Updated {len(rows)} rows. birth_name set to NULL.")


if __name__ == "__main__":
    main()
