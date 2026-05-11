#!/usr/bin/env python3
"""Bulk import Vietnamese persons + family edges from Wikidata SPARQL.

Two passes:
  1) Fetch all human entities tagged Vietnamese citizenship OR Vietnamese
     ethnic group (paginated). Insert as 'wikidata' source persons.
  2) For each family property (P22, P25, P26, P40, P3373), fetch all edges
     where the subject is in our VN set. Auto-create the target as a
     referenced person if not already in DB.

Idempotent: uses existing slug_to_uuid + canonical_relation_uuid system
from seed_db.py / import_wiki_vi.py so re-runs don't duplicate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Iterable

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "wikipath.duckdb"
NS = uuid.UUID("8b0e3c4f-1234-5000-8000-000000000000")
USER_AGENT = "wikipath-importer/0.1 (https://github.com/piazlabs/wikipath; sonpiaz@gmail.com)"
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

SYMMETRIC_KINDS = {
    "spouse", "concubine",
    "sibling_full", "sibling_paternal", "sibling_maternal",
}

# ─────────── UUID helpers (mirror seed_db.py) ───────────

def slug_from_qid(qid: str) -> str:
    return f"wd-{qid.lower()}"


def slug_from_name(name: str) -> str:
    pre = name.replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", pre)
    no_accent = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", no_accent).strip("-").lower()
    return slug or hashlib.md5(name.encode()).hexdigest()[:10]


def slug_to_uuid(slug: str) -> uuid.UUID:
    return uuid.uuid5(NS, slug)


def canonicalize_relation(from_id, kind, to_id):
    if kind in SYMMETRIC_KINDS and str(from_id) > str(to_id):
        return to_id, from_id
    return from_id, to_id


def relation_uuid(from_id, kind, to_id):
    fa, fb = canonicalize_relation(from_id, kind, to_id)
    return uuid.uuid5(NS, f"rel|{fa}|{kind}|{fb}")


# ─────────── SPARQL client ───────────

def sparql(query: str, retries: int = 3) -> dict:
    body = urllib.parse.urlencode({"query": query, "format": "json"}).encode()
    delay = 2.0
    for attempt in range(retries):
        req = urllib.request.Request(
            SPARQL_ENDPOINT,
            data=body,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/sparql-results+json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.load(resp)
        except Exception as e:
            if attempt == retries - 1:
                raise
            print(f"  sparql retry {attempt+1}/{retries} after {delay}s ({e})", file=sys.stderr)
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")


def value_qid(binding: dict, key: str) -> str | None:
    v = binding.get(key)
    if not v:
        return None
    uri = v["value"]
    m = re.search(r"/(Q\d+)$", uri)
    return m.group(1) if m else None


def value_lit(binding: dict, key: str) -> str | None:
    v = binding.get(key)
    return v["value"] if v else None


def parse_year(s: str | None) -> int | None:
    if not s:
        return None
    m = re.match(r"(-?\d{1,4})-\d{2}-\d{2}", s)
    if m:
        return int(m.group(1))
    return None


# ─────────── Phase 1: VN persons ───────────

PERSONS_QUERY = """
SELECT DISTINCT ?p ?pLabel ?birth ?death ?gender ?birthPlaceLabel
WHERE {
  {
    SELECT DISTINCT ?p WHERE {
      ?p wdt:P31 wd:Q5 .
      { ?p wdt:P27 wd:Q881 } UNION { ?p wdt:P172 wd:Q126480 }
    }
    LIMIT %d OFFSET %d
  }
  OPTIONAL { ?p wdt:P569 ?birth }
  OPTIONAL { ?p wdt:P570 ?death }
  OPTIONAL { ?p wdt:P21 ?gender }
  OPTIONAL { ?p wdt:P19 ?birthPlace }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "vi,en" }
}
"""


GENDER_MAP = {
    "Q6581097": "male",   # male
    "Q6581072": "female", # female
    "Q1097630": "intersex",
    "Q1052281": "trans female",
    "Q2449503": "trans male",
}


def fetch_vn_persons(page_size: int = 500, max_pages: int = 20) -> list[dict]:
    """Returns list of {qid, label, birth_y, death_y, gender, birth_place}."""
    all_rows = []
    seen_qids = set()
    for page in range(max_pages):
        q = PERSONS_QUERY % (page_size, page * page_size)
        print(f"[persons] page {page+1} (offset {page*page_size})…", file=sys.stderr)
        data = sparql(q)
        bindings = data.get("results", {}).get("bindings", [])
        if not bindings:
            print(f"[persons] empty page → stop", file=sys.stderr)
            break
        new_count = 0
        for b in bindings:
            qid = value_qid(b, "p")
            if not qid or qid in seen_qids:
                continue
            seen_qids.add(qid)
            label = value_lit(b, "pLabel") or qid
            if label.startswith("Q") and label[1:].isdigit():
                continue  # skip rows where label = QID (no label)
            row = {
                "qid": qid,
                "label": label,
                "birth_y": parse_year(value_lit(b, "birth")),
                "death_y": parse_year(value_lit(b, "death")),
                "gender": GENDER_MAP.get(value_qid(b, "gender") or "", "unknown"),
                "birth_place": value_lit(b, "birthPlaceLabel"),
            }
            all_rows.append(row)
            new_count += 1
        print(f"[persons] page {page+1}: +{new_count} (total {len(all_rows)})", file=sys.stderr)
        if new_count == 0:
            break
        time.sleep(0.5)
    return all_rows


# ─────────── Phase 2: family edges ───────────

# Wikidata family properties → schema kind
FAMILY_PROPS = {
    "P22": "parent_father",  # father; from=child, to=father
    "P25": "parent_mother",
    "P26": "spouse",
    "P40": "child_birth",     # child of subject; we'll convert to parent_father (target=child has parent=subject)
    "P3373": "sibling_full",
}


EDGES_QUERY = """
SELECT ?from ?fromLabel ?to ?toLabel
WHERE {
  ?from wdt:%s ?to .
  { ?from wdt:P27 wd:Q881 } UNION { ?from wdt:P172 wd:Q126480 }
}
LIMIT %d OFFSET %d
"""


def fetch_edges(prop: str, page_size: int = 1000, max_pages: int = 20) -> list[dict]:
    out = []
    for page in range(max_pages):
        q = EDGES_QUERY % (prop, page_size, page * page_size)
        print(f"[edges {prop}] page {page+1} (offset {page*page_size})…", file=sys.stderr)
        data = sparql(q)
        bindings = data.get("results", {}).get("bindings", [])
        if not bindings:
            break
        for b in bindings:
            fr = value_qid(b, "from")
            to = value_qid(b, "to")
            fr_lbl = value_lit(b, "fromLabel")
            to_lbl = value_lit(b, "toLabel")
            if not fr or not to:
                continue
            out.append({
                "from_qid": fr, "from_label": fr_lbl,
                "to_qid": to, "to_label": to_lbl,
            })
        print(f"[edges {prop}] page {page+1}: +{len(bindings)} (total {len(out)})", file=sys.stderr)
        if len(bindings) < page_size:
            break
        time.sleep(0.5)
    return out


# ─────────── DB store ───────────

class Store:
    def __init__(self, con):
        self.con = con
        self.qid_to_id = {}
        rows = self.con.execute(
            "SELECT id, wikidata_qid FROM person WHERE wikidata_qid IS NOT NULL"
        ).fetchall()
        for pid, qid in rows:
            self.qid_to_id[qid] = pid

    def upsert_person(self, qid: str, label: str, *, birth_y=None, death_y=None,
                      gender="unknown", birth_place=None, source="wikidata") -> uuid.UUID:
        if qid in self.qid_to_id:
            pid = self.qid_to_id[qid]
            # Light update for missing fields (don't clobber seed data)
            updates = []
            args = []
            if birth_y:
                updates.append("birth_date_y = COALESCE(birth_date_y, ?)")
                args.append(birth_y)
            if death_y:
                updates.append("death_date_y = COALESCE(death_date_y, ?)")
                args.append(death_y)
            if gender and gender != "unknown":
                updates.append("gender = CASE WHEN gender = 'unknown' THEN ? ELSE gender END")
                args.append(gender)
            if birth_place:
                updates.append("birth_place = COALESCE(birth_place, ?)")
                args.append(birth_place)
            if updates:
                args.append(pid)
                self.con.execute(
                    f"UPDATE person SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    args,
                )
            return pid

        # New person — derive UUID from QID-based slug for stability
        slug = slug_from_qid(qid)
        pid = slug_to_uuid(slug)
        # Determine era from birth year
        era = "1900-1950"
        if birth_y:
            if birth_y < 1500: era = "pre-1500"
            elif birth_y < 1900: era = "1500-1900"
            elif birth_y < 1950: era = "1900-1950"
            else: era = "1950+"
        self.con.execute(
            """
            INSERT INTO person (
                id, wikidata_qid, birth_name, era, gender, historicity,
                trust_score, primary_source,
                birth_date_y, death_date_y, birth_place
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT (id) DO NOTHING
            """,
            [
                pid, qid, label, era, gender, "confirmed",
                85, source,
                birth_y, death_y, birth_place,
            ],
        )
        self.qid_to_id[qid] = pid
        return pid

    def find_or_stub(self, qid: str, label: str | None) -> uuid.UUID:
        """Get existing person by QID, or insert a minimal stub for referenced
        non-VN family members."""
        if qid in self.qid_to_id:
            return self.qid_to_id[qid]
        return self.upsert_person(
            qid, label or qid, source="wikidata-referenced"
        )

    def upsert_relation(self, kind: str, from_id, to_id, *, source_kind="wikidata",
                        source_ref=None, confidence=85):
        if from_id == to_id:
            return
        rid = relation_uuid(from_id, kind, to_id)
        from_id, to_id = canonicalize_relation(from_id, kind, to_id)
        self.con.execute(
            """
            INSERT INTO relation (id, from_person_id, to_person_id, kind,
                                  source_kind, source_ref, confidence)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT (id) DO UPDATE SET
                source_kind = excluded.source_kind,
                source_ref = excluded.source_ref,
                confidence = GREATEST(relation.confidence, excluded.confidence)
            """,
            [rid, from_id, to_id, kind, source_kind, source_ref, confidence],
        )


# ─────────── Pipeline ───────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--max-person-pages", type=int, default=20)
    ap.add_argument("--max-edge-pages", type=int, default=10)
    ap.add_argument("--skip-persons", action="store_true")
    ap.add_argument("--skip-edges", action="store_true")
    args = ap.parse_args()

    con = duckdb.connect(str(args.db))
    store = Store(con)

    initial_persons = con.execute("SELECT COUNT(*) FROM person").fetchone()[0]
    initial_relations = con.execute("SELECT COUNT(*) FROM relation").fetchone()[0]
    print(f"\nstart: {initial_persons} persons, {initial_relations} relations")

    if not args.skip_persons:
        print("\n=== Phase 1: VN persons ===")
        persons = fetch_vn_persons(max_pages=args.max_person_pages)
        print(f"\nfetched {len(persons)} VN persons. inserting…")
        for i, p in enumerate(persons, 1):
            store.upsert_person(
                p["qid"], p["label"],
                birth_y=p["birth_y"], death_y=p["death_y"],
                gender=p["gender"], birth_place=p["birth_place"],
            )
            if i % 200 == 0:
                con.execute("CHECKPOINT")
                print(f"  inserted {i}/{len(persons)}")
        con.execute("CHECKPOINT")
        mid_persons = con.execute("SELECT COUNT(*) FROM person").fetchone()[0]
        print(f"after persons: {mid_persons} (+{mid_persons - initial_persons})")

    if not args.skip_edges:
        print("\n=== Phase 2: family edges ===")
        edge_total = 0
        edge_skipped = 0
        for prop, kind in FAMILY_PROPS.items():
            print(f"\n--- property {prop} ({kind}) ---")
            edges = fetch_edges(prop, max_pages=args.max_edge_pages)
            inserted = 0
            for e in edges:
                fr_id = store.qid_to_id.get(e["from_qid"])
                if not fr_id:
                    edge_skipped += 1
                    continue  # subject not in our VN set (shouldn't happen)
                to_id = store.find_or_stub(e["to_qid"], e["to_label"])

                # P40 means "subject HAS child target"; convert to parent_father with reversed direction
                if prop == "P40":
                    store.upsert_relation(
                        "parent_father", to_id, fr_id,
                        source_ref=f"wd:{e['from_qid']}>P40>{e['to_qid']}",
                    )
                else:
                    store.upsert_relation(
                        kind, fr_id, to_id,
                        source_ref=f"wd:{e['from_qid']}>{prop}>{e['to_qid']}",
                    )
                inserted += 1
            edge_total += inserted
            con.execute("CHECKPOINT")
            print(f"  {prop}: inserted {inserted}/{len(edges)}")
        print(f"\nedges done: {edge_total} inserted, {edge_skipped} skipped")

    final_persons = con.execute("SELECT COUNT(*) FROM person").fetchone()[0]
    final_relations = con.execute("SELECT COUNT(*) FROM relation").fetchone()[0]
    final_qids = con.execute("SELECT COUNT(*) FROM person WHERE wikidata_qid IS NOT NULL").fetchone()[0]
    print()
    print(f"PERSONS:    {initial_persons} → {final_persons}   (+{final_persons - initial_persons})")
    print(f"WITH QID:   {final_qids}")
    print(f"RELATIONS:  {initial_relations} → {final_relations} (+{final_relations - initial_relations})")


if __name__ == "__main__":
    main()
