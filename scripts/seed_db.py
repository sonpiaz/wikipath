#!/usr/bin/env python3
"""Bootstrap wikipath.duckdb from schema + YAML seed.

Idempotent: deterministic UUIDs from slug. Re-running drops & rebuilds.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import uuid
from pathlib import Path

import duckdb
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_FILE = ROOT / "internal" / "schema" / "001_init.sql"
SEED_FILE = ROOT / "data" / "seed-vi.yml"
DEFAULT_DB = ROOT / "wikipath.duckdb"

NS = uuid.UUID("8b0e3c4f-1234-5000-8000-000000000000")


def slug_to_uuid(slug: str) -> uuid.UUID:
    return uuid.uuid5(NS, slug)


SYMMETRIC_KINDS = {
    "spouse", "concubine",
    "sibling_full", "sibling_paternal", "sibling_maternal",
}


def canonicalize_relation(from_id: uuid.UUID, kind: str, to_id: uuid.UUID):
    if kind in SYMMETRIC_KINDS and str(from_id) > str(to_id):
        return to_id, from_id
    return from_id, to_id


def deterministic_relation_uuid(from_id: uuid.UUID, kind: str, to_id: uuid.UUID) -> uuid.UUID:
    fa, fb = canonicalize_relation(from_id, kind, to_id)
    return uuid.uuid5(NS, f"rel|{fa}|{kind}|{fb}")


def deterministic_name_uuid(person_id: uuid.UUID, name: str, kind: str) -> uuid.UUID:
    return uuid.uuid5(NS, f"name|{person_id}|{kind}|{name}")


def load_schema(con: duckdb.DuckDBPyConnection):
    sql = SCHEMA_FILE.read_text()
    con.execute(sql)


def reset_tables(con: duckdb.DuckDBPyConnection):
    for table in ("contribution_log", "contributor", "relation", "name", "person"):
        con.execute(f"DELETE FROM {table}")


def insert_person(con: duckdb.DuckDBPyConnection, person: dict):
    pid = slug_to_uuid(person["id"])
    con.execute(
        """
        INSERT INTO person (
            id, wikidata_qid, wikipedia_vi_url, birth_name,
            current_family_name, original_family_name, lineage_branch,
            era, dynasty,
            birth_date_y, birth_date_m, birth_date_d,
            death_date_y, death_date_m, death_date_d,
            birth_place, death_place,
            bio_short, bio_full, avatar_url,
            historicity, gender, is_living, consent_status,
            trust_score, primary_source
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        [
            pid,
            person.get("qid"),
            person.get("wiki_vi"),
            person["birth_name"],
            person.get("family_name"),
            person.get("original_family_name"),
            person.get("lineage_branch"),
            person["era"],
            person.get("dynasty"),
            person.get("birth_y"), person.get("birth_m"), person.get("birth_d"),
            person.get("death_y"), person.get("death_m"), person.get("death_d"),
            person.get("birth_place"),
            person.get("death_place"),
            person.get("bio_short"),
            person.get("bio_full"),
            person.get("avatar_url"),
            person.get("historicity", "confirmed"),
            person.get("gender", "unknown"),
            bool(person.get("is_living", False)),
            person.get("consent_status", "public"),
            int(person.get("trust_score", 80)),
            person.get("primary_source"),
        ],
    )
    return pid


def insert_names(con: duckdb.DuckDBPyConnection, person: dict):
    pid = slug_to_uuid(person["id"])
    for entry in person.get("names", []):
        con.execute(
            """
            INSERT INTO name (id, person_id, name, kind, period_start, period_end, language)
            VALUES (?,?,?,?,?,?,?)
            """,
            [
                deterministic_name_uuid(pid, entry["name"], entry["kind"]),
                pid,
                entry["name"],
                entry["kind"],
                entry.get("period_start"),
                entry.get("period_end"),
                entry.get("language", "vi"),
            ],
        )


def insert_relation(con: duckdb.DuckDBPyConnection, rel: dict, slug_set: set):
    for k in ("from", "to"):
        if rel[k] not in slug_set:
            print(f"WARN: relation references unknown slug {rel[k]!r}: {rel}", file=sys.stderr)
            return
    from_id = slug_to_uuid(rel["from"])
    to_id = slug_to_uuid(rel["to"])
    rid = deterministic_relation_uuid(from_id, rel["kind"], to_id)
    from_id, to_id = canonicalize_relation(from_id, rel["kind"], to_id)
    con.execute(
        """
        INSERT INTO relation (
            id, from_person_id, to_person_id, kind, rank,
            period_start_y, period_end_y,
            source_kind, source_ref, confidence
        ) VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        [
            rid,
            from_id,
            to_id,
            rel["kind"],
            rel.get("rank"),
            rel.get("period_start_y"),
            rel.get("period_end_y"),
            rel.get("source_kind", "seed"),
            rel.get("source_ref", "data/seed-vi.yml"),
            int(rel.get("confidence", 90)),
        ],
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--reset", action="store_true", help="drop and recreate tables")
    args = ap.parse_args()

    seed = yaml.safe_load(SEED_FILE.read_text())
    persons = seed["persons"]
    relations = seed["relations"]
    print(f"loading {len(persons)} persons, {len(relations)} relations")

    if args.reset and args.db.exists():
        args.db.unlink()
        print(f"removed existing {args.db}")

    con = duckdb.connect(str(args.db))
    load_schema(con)

    reset_tables(con)

    slug_set = set()
    for p in persons:
        slug_set.add(p["id"])
        insert_person(con, p)
        insert_names(con, p)

    for r in relations:
        insert_relation(con, r, slug_set)

    con.execute("CHECKPOINT")
    n_person = con.execute("SELECT COUNT(*) FROM person").fetchone()[0]
    n_name   = con.execute("SELECT COUNT(*) FROM name").fetchone()[0]
    n_rel    = con.execute("SELECT COUNT(*) FROM relation").fetchone()[0]
    print(f"persons={n_person} names={n_name} relations={n_rel}")
    print(f"db: {args.db}")


if __name__ == "__main__":
    main()
