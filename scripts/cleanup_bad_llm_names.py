#!/usr/bin/env python3
"""Backfill cleanup — remove LLM-enriched persons + relations whose
`birth_name` fails the v1 name validator (see SPEC §4.8).

Strategy:
  1. Scan every person where primary_source='llm_enrich'.
  2. Apply `is_valid_person_name()` from enrich_async.
  3. Collect ids of invalid persons.
  4. Delete relations where either endpoint is invalid.
  5. Delete the invalid person rows themselves.
  6. Print before/after counts.

Defaults to --dry-run. Pass --apply to commit changes.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.enrich_async import clean_person_name, is_valid_person_name


DEFAULT_DB = ROOT / "wikipath.duckdb"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--apply", action="store_true",
                    help="commit deletions (default: dry-run, no changes)")
    args = ap.parse_args()

    con = duckdb.connect(str(args.db),
                         read_only=not args.apply)

    persons_before = con.execute("SELECT COUNT(*) FROM person").fetchone()[0]
    rels_before = con.execute("SELECT COUNT(*) FROM relation").fetchone()[0]
    llm_persons_before = con.execute(
        "SELECT COUNT(*) FROM person WHERE primary_source = 'llm_enrich'"
    ).fetchone()[0]
    llm_rels_before = con.execute(
        "SELECT COUNT(*) FROM relation WHERE source_kind = 'llm_enrich'"
    ).fetchone()[0]

    print(f"BEFORE: persons={persons_before}  relations={rels_before}")
    print(f"        llm_persons={llm_persons_before}  llm_relations={llm_rels_before}")
    print()

    # Find invalid LLM-source persons
    rows = con.execute(
        "SELECT id, birth_name FROM person WHERE primary_source = 'llm_enrich'"
    ).fetchall()

    invalid_ids = []
    invalid_names = []
    for pid, name in rows:
        cleaned = clean_person_name(name)
        if not is_valid_person_name(cleaned):
            invalid_ids.append(pid)
            invalid_names.append((pid, name, cleaned))

    print(f"Found {len(invalid_ids)} invalid LLM-source persons "
          f"({len(invalid_ids) * 100 / max(1, llm_persons_before):.2f}% of llm pool)")
    print()
    if invalid_names:
        print("Sample (up to 20):")
        for pid, raw, cleaned in invalid_names[:20]:
            print(f"  - {raw!r}  (cleaned: {cleaned!r})")
        print()

    if not invalid_ids:
        print("Nothing to clean. Exiting.")
        return

    # Count relations that reference any invalid person
    placeholders = ",".join("?" * len(invalid_ids))
    rel_count = con.execute(
        f"SELECT COUNT(*) FROM relation "
        f"WHERE from_person_id IN ({placeholders}) "
        f"   OR to_person_id   IN ({placeholders})",
        invalid_ids + invalid_ids,
    ).fetchone()[0]
    print(f"{rel_count} relations reference an invalid person.")

    # Find any *other* person rows that still reference these via relations
    # (i.e., valid persons whose only relation is to a bad stub). They keep
    # their identity; we only delete the bad endpoints.

    if not args.apply:
        print()
        print("DRY RUN — pass --apply to commit.")
        return

    # Delete relations first (FK-style integrity even though FKs disabled)
    con.execute(
        f"DELETE FROM relation "
        f"WHERE from_person_id IN ({placeholders}) "
        f"   OR to_person_id   IN ({placeholders})",
        invalid_ids + invalid_ids,
    )
    # Delete name rows pointing at invalid persons (some scripts may have
    # populated alt-names; safe to delete since person is bogus)
    con.execute(
        f"DELETE FROM name WHERE person_id IN ({placeholders})",
        invalid_ids,
    )
    # Delete the invalid persons themselves
    con.execute(
        f"DELETE FROM person WHERE id IN ({placeholders})",
        invalid_ids,
    )
    con.execute("CHECKPOINT")

    persons_after = con.execute("SELECT COUNT(*) FROM person").fetchone()[0]
    rels_after = con.execute("SELECT COUNT(*) FROM relation").fetchone()[0]
    llm_persons_after = con.execute(
        "SELECT COUNT(*) FROM person WHERE primary_source = 'llm_enrich'"
    ).fetchone()[0]
    llm_rels_after = con.execute(
        "SELECT COUNT(*) FROM relation WHERE source_kind = 'llm_enrich'"
    ).fetchone()[0]

    print()
    print(f"AFTER:  persons={persons_after}  relations={rels_after}")
    print(f"        llm_persons={llm_persons_after}  llm_relations={llm_rels_after}")
    print()
    print(f"Removed: {persons_before - persons_after} persons, "
          f"{rels_before - rels_after} relations.")


if __name__ == "__main__":
    main()
