#!/usr/bin/env python3
"""Import family relations from Vietnamese Wikipedia infoboxes.

Reads a list of page titles, fetches each via the MediaWiki API, parses
the {{Thông tin ...}} infobox, extracts family fields (cha, mẹ, vợ, chồng,
con, anh chị em), and writes new persons/relations to wikipath.duckdb.

Idempotent: matches by Wikidata QID first, then by exact birth_name.
Creates new community-tier persons for referenced people not yet in DB.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "wikipath.duckdb"
NS = uuid.UUID("8b0e3c4f-1234-5000-8000-000000000000")
USER_AGENT = "wikipath-importer/0.1 (https://github.com/sonpiaz/wikipath; sonpiaz@gmail.com)"
API = "https://vi.wikipedia.org/w/api.php"

# ─────────── HTTP helpers ───────────

def http_get_json(url: str, params: dict, retries: int = 3) -> dict:
    qs = urllib.parse.urlencode(params)
    full = f"{url}?{qs}"
    delay = 1.0
    for attempt in range(retries):
        req = urllib.request.Request(full, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                import json
                return json.load(resp)
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")


def fetch_page(title: str) -> dict | None:
    """Returns dict with {title, wikitext, qid} or None on miss."""
    data = http_get_json(API, {
        "action": "query",
        "format": "json",
        "prop": "revisions|pageprops",
        "rvprop": "content",
        "rvslots": "main",
        "ppprop": "wikibase_item",
        "redirects": "1",
        "titles": title,
    })
    pages = data.get("query", {}).get("pages", {})
    for pid, page in pages.items():
        if pid == "-1" or "missing" in page:
            return None
        revs = page.get("revisions", [])
        if not revs:
            return None
        wikitext = revs[0]["slots"]["main"]["*"]
        qid = page.get("pageprops", {}).get("wikibase_item")
        return {"title": page["title"], "wikitext": wikitext, "qid": qid}
    return None


# ─────────── Infobox extraction ───────────

INFOBOX_PATTERN = re.compile(
    r"\{\{\s*(?:Thông tin|Hộp thông tin|Infobox)\b[^|}\n]*", re.IGNORECASE
)


def find_infobox_block(wikitext: str) -> str | None:
    """Find the first {{Thông tin ...}} template and return its full content
    by balanced-brace matching."""
    m = INFOBOX_PATTERN.search(wikitext)
    if not m:
        return None
    start = m.start()
    depth = 0
    i = start
    while i < len(wikitext):
        if wikitext[i:i+2] == "{{":
            depth += 1
            i += 2
        elif wikitext[i:i+2] == "}}":
            depth -= 1
            i += 2
            if depth == 0:
                return wikitext[start:i]
        else:
            i += 1
    return None


def split_top_level_pipes(s: str) -> list[str]:
    """Split a template body by '|' but respect nested {{}} and [[]]."""
    parts = []
    depth_brace = 0
    depth_bracket = 0
    buf = []
    i = 0
    while i < len(s):
        c2 = s[i:i+2]
        if c2 == "{{":
            depth_brace += 1
            buf.append(c2); i += 2
        elif c2 == "}}":
            depth_brace -= 1
            buf.append(c2); i += 2
        elif c2 == "[[":
            depth_bracket += 1
            buf.append(c2); i += 2
        elif c2 == "]]":
            depth_bracket -= 1
            buf.append(c2); i += 2
        elif s[i] == "|" and depth_brace == 0 and depth_bracket == 0:
            parts.append("".join(buf))
            buf = []
            i += 1
        else:
            buf.append(s[i]); i += 1
    parts.append("".join(buf))
    return parts


def parse_infobox(infobox_block: str) -> dict[str, str]:
    """{{Thông tin X | a = 1 | b = 2}} → {a: '1', b: '2'} (lowercased keys)."""
    inner = infobox_block.removeprefix("{{").removesuffix("}}").strip()
    parts = split_top_level_pipes(inner)
    if not parts:
        return {}
    fields = {}
    for part in parts[1:]:  # parts[0] = "Thông tin X"
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        key = k.strip().lower()
        val = v.strip()
        if val:
            fields[key] = val
    return fields


# ─────────── Wikitext value parsers ───────────

LINK_PATTERN = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]+?))?\]\]")
TEMPLATE_PATTERN = re.compile(r"\{\{([^{}|]+)((?:\|[^{}]*)*)\}\}")
HTML_TAG = re.compile(r"<[^>]+>")
REF_PATTERN = re.compile(r"<ref[^>]*>.*?</ref>", re.DOTALL)
COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)


def strip_refs_and_comments(s: str) -> str:
    s = COMMENT_PATTERN.sub("", s)
    s = REF_PATTERN.sub("", s)
    return s


def extract_links(value: str) -> list[tuple[str, str]]:
    """Return [(target, display)] from [[Target|Display]] or [[Target]]."""
    out = []
    for m in LINK_PATTERN.finditer(value):
        target = m.group(1).strip()
        display = (m.group(2) or m.group(1)).strip()
        # Skip section anchors and image links
        if target.startswith(("#", "Tập tin:", "File:", "Image:")):
            continue
        out.append((target, display))
    return out


def split_multivalue(value: str) -> list[str]:
    """Split a field that may contain multiple persons separated by <br>, ',' or templates."""
    cleaned = strip_refs_and_comments(value)
    cleaned = re.sub(r"<br\s*/?\s*>", "\n", cleaned, flags=re.IGNORECASE)
    cleaned = HTML_TAG.sub("", cleaned)
    parts = re.split(r"\n|,(?![^\[]*\]\])", cleaned)
    return [p.strip() for p in parts if p.strip()]


def extract_year(value: str) -> int | None:
    s = strip_refs_and_comments(value)
    # {{ngày sinh và tuổi|y|m|d}} or {{ngày mất và tuổi|y|m|d|by|bm|bd}} or similar
    tpl = TEMPLATE_PATTERN.search(s)
    if tpl:
        args = tpl.group(2).split("|")[1:]
        if args and args[0].isdigit() and len(args[0]) == 4:
            return int(args[0])
    # plain 4-digit year fallback
    m = re.search(r"\b(1\d{3}|20\d{2})\b", s)
    if m:
        return int(m.group(1))
    return None


def extract_full_date(value: str) -> tuple[int | None, int | None, int | None]:
    s = strip_refs_and_comments(value)
    tpl = TEMPLATE_PATTERN.search(s)
    if tpl:
        args = [a.strip() for a in tpl.group(2).split("|")[1:]]
        if len(args) >= 3 and args[0].isdigit() and args[1].isdigit() and args[2].isdigit():
            return (int(args[0]), int(args[1]), int(args[2]))
        if len(args) >= 1 and args[0].isdigit() and len(args[0]) == 4:
            return (int(args[0]), None, None)
    y = extract_year(s)
    return (y, None, None)


# ─────────── Era/dynasty inference ───────────

DYNASTY_KEYWORDS = {
    "Lý": "ly", "nhà Lý": "ly",
    "Trần": "tran", "nhà Trần": "tran",
    "Lê": "le", "Hậu Lê": "le", "nhà Hậu Lê": "le", "nhà Lê": "le",
    "Mạc": "mac",
    "Trịnh": "trinh",
    "Tây Sơn": "tay-son",
    "Nguyễn": "nguyen", "nhà Nguyễn": "nguyen",
}


def infer_era(birth_y: int | None, death_y: int | None) -> str:
    y = birth_y or death_y
    if y is None:
        return "1900-1950"  # default unknown
    if y < 1500: return "pre-1500"
    if y < 1900: return "1500-1900"
    if y < 1950: return "1900-1950"
    return "1950+"


def infer_dynasty(value: str) -> str | None:
    v = value.lower()
    for kw, dyn in DYNASTY_KEYWORDS.items():
        if kw.lower() in v:
            return dyn
    return None


# ─────────── DB layer ───────────

def slug_from_name(name: str) -> str:
    # Vietnamese-specific: NFD doesn't decompose đ/Đ. Replace before normalize.
    pre = name.replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", pre)
    no_accent = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", no_accent).strip("-").lower()
    return slug or hashlib.md5(name.encode()).hexdigest()[:10]


def slug_to_uuid(slug: str) -> uuid.UUID:
    return uuid.uuid5(NS, slug)


SYMMETRIC_KINDS = {
    "spouse", "concubine",
    "sibling_full", "sibling_paternal", "sibling_maternal",
}


def canonicalize_relation(from_id: uuid.UUID, kind: str, to_id: uuid.UUID
                          ) -> tuple[uuid.UUID, uuid.UUID]:
    """For symmetric kinds, always store with the lexicographically smaller
    id as `from`. Asymmetric kinds (parent_*, child_*) keep caller order."""
    if kind in SYMMETRIC_KINDS and str(from_id) > str(to_id):
        return to_id, from_id
    return from_id, to_id


def relation_uuid(from_id: uuid.UUID, kind: str, to_id: uuid.UUID) -> uuid.UUID:
    fa, fb = canonicalize_relation(from_id, kind, to_id)
    return uuid.uuid5(NS, f"rel|{fa}|{kind}|{fb}")


def name_uuid(person_id: uuid.UUID, name: str, kind: str) -> uuid.UUID:
    return uuid.uuid5(NS, f"name|{person_id}|{kind}|{name}")


class Store:
    def __init__(self, con: duckdb.DuckDBPyConnection):
        self.con = con
        self.qid_index = {}
        self.name_index = {}
        self._reload_indexes()

    def _reload_indexes(self):
        rows = self.con.execute(
            "SELECT id, wikidata_qid, birth_name FROM person"
        ).fetchall()
        self.qid_index = {r[1]: r[0] for r in rows if r[1]}
        self.name_index = {r[2]: r[0] for r in rows}

    def find_or_create(self, name: str, qid: str | None = None,
                       source: str = "wikipedia_vi") -> tuple[uuid.UUID, bool]:
        """Returns (person_id, was_created)."""
        if qid and qid in self.qid_index:
            return self.qid_index[qid], False
        if name in self.name_index:
            return self.name_index[name], False
        slug = slug_from_name(name)
        pid = slug_to_uuid(slug)
        # Final check: pid may already exist in DB if a previously-seeded row
        # has a different birth_name but identical slug after diacritic strip.
        existing = self.con.execute(
            "SELECT birth_name, wikidata_qid FROM person WHERE id = ?", [pid]
        ).fetchone()
        if existing:
            self.name_index[existing[0]] = pid
            if existing[1]:
                self.qid_index[existing[1]] = pid
            self.name_index[name] = pid
            return pid, False
        self.con.execute(
            """
            INSERT INTO person (id, wikidata_qid, birth_name, era, gender,
                                historicity, trust_score, primary_source)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT (id) DO NOTHING
            """,
            [pid, qid, name, "1900-1950", "unknown", "probable", 60, source],
        )
        if qid:
            self.qid_index[qid] = pid
        self.name_index[name] = pid
        return pid, True

    def update_person(self, pid: uuid.UUID, fields: dict):
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        self.con.execute(f"UPDATE person SET {cols}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                         list(fields.values()) + [pid])

    def upsert_relation(self, kind: str,
                        from_id: uuid.UUID, to_id: uuid.UUID,
                        rank: int | None = None, source_kind: str = "wikipedia_vi",
                        source_ref: str | None = None, confidence: int = 75):
        if from_id == to_id:
            return  # don't self-link
        rid = relation_uuid(from_id, kind, to_id)
        from_id, to_id = canonicalize_relation(from_id, kind, to_id)
        self.con.execute(
            """
            INSERT INTO relation (id, from_person_id, to_person_id, kind, rank,
                                  source_kind, source_ref, confidence)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT (id) DO UPDATE SET
                rank = excluded.rank,
                source_kind = excluded.source_kind,
                source_ref = excluded.source_ref,
                confidence = excluded.confidence
            """,
            [rid, from_id, to_id, kind, rank, source_kind, source_ref, confidence],
        )

    def add_name(self, person_id: uuid.UUID, name: str, kind: str):
        nid = name_uuid(person_id, name, kind)
        self.con.execute(
            """
            INSERT INTO name (id, person_id, name, kind, language)
            VALUES (?,?,?,?,?)
            ON CONFLICT (id) DO NOTHING
            """,
            [nid, person_id, name, kind, "vi"],
        )


# ─────────── Pipeline ───────────

PARENT_FIELD = {"cha", "cha đẻ", "cha mẹ", "father"}
MOTHER_FIELD = {"mẹ", "mẹ đẻ", "mother"}
SPOUSE_FIELD = {"vợ", "chồng", "phối ngẫu", "hôn phối", "hoàng hậu",
                "spouse", "partner", "spouses"}
CHILD_FIELD = {"con", "con cái", "children", "child"}
SIBLING_FIELD = {"anh chị em", "anh em", "anh em ruột",
                 "siblings", "relations", "relatives"}


def import_one(store: Store, title: str, *, verbose: bool = False) -> dict:
    page = fetch_page(title)
    if not page:
        return {"title": title, "found": False}

    block = find_infobox_block(page["wikitext"])
    if not block:
        return {"title": title, "found": True, "infobox": False}

    fields = parse_infobox(block)
    canonical_name = (fields.get("tên") or fields.get("tên đầy đủ")
                      or page["title"])
    canonical_name = strip_refs_and_comments(canonical_name)
    canonical_name = HTML_TAG.sub("", canonical_name).strip()

    # Resolve / create primary person
    primary_slug = slug_from_name(canonical_name)
    pid, created = store.find_or_create(canonical_name, qid=page["qid"])

    # Update primary person fields
    updates: dict = {}
    if page["qid"]:
        updates["wikidata_qid"] = page["qid"]
    updates["wikipedia_vi_url"] = f"https://vi.wikipedia.org/wiki/{urllib.parse.quote(page['title'].replace(' ', '_'))}"

    by, bm, bd = extract_full_date(fields.get("sinh", ""))
    dy, dm, dd = extract_full_date(fields.get("mất", ""))
    if by: updates["birth_date_y"] = by
    if bm: updates["birth_date_m"] = bm
    if bd: updates["birth_date_d"] = bd
    if dy: updates["death_date_y"] = dy
    if dm: updates["death_date_m"] = dm
    if dd: updates["death_date_d"] = dd

    era_inferred = infer_era(by, dy)
    updates["era"] = era_inferred

    dyn_field = fields.get("hoàng tộc") or fields.get("triều đại") or ""
    dyn = infer_dynasty(dyn_field)
    if dyn:
        updates["dynasty"] = dyn

    bp_raw = fields.get("nơi sinh", "")
    if bp_raw:
        bp_clean = HTML_TAG.sub("", strip_refs_and_comments(bp_raw))
        bp_clean = LINK_PATTERN.sub(lambda m: m.group(2) or m.group(1), bp_clean).strip()
        if bp_clean:
            updates["birth_place"] = bp_clean

    updates["trust_score"] = 80
    updates["primary_source"] = updates["wikipedia_vi_url"]
    store.update_person(pid, updates)

    # Alt names from "tên đầy đủ", "tên gốc", "tước hiệu"
    alts = []
    if fields.get("tên đầy đủ") and fields.get("tên đầy đủ") != canonical_name:
        alts.append((fields["tên đầy đủ"], "birth"))
    if fields.get("tên gốc"):
        alts.append((fields["tên gốc"], "birth"))
    if fields.get("tước hiệu"):
        alts.append((HTML_TAG.sub("", strip_refs_and_comments(fields["tước hiệu"])).split("\n")[0].strip(), "courtesy"))
    if fields.get("miếu hiệu"):
        alts.append((fields["miếu hiệu"], "temple"))
    if fields.get("thụy hiệu"):
        alts.append((HTML_TAG.sub("", strip_refs_and_comments(fields["thụy hiệu"])).split("\n")[0].strip(), "posthumous"))

    for alt_name, kind in alts:
        if alt_name and len(alt_name) < 200:
            store.add_name(pid, alt_name, kind)

    # Relations
    rel_count = {"father": 0, "mother": 0, "spouse": 0, "child": 0, "sibling": 0, "skipped": 0}

    def resolve_links_in_field(value: str) -> list[tuple[str, str | None]]:
        """Return [(name, qid_or_none)] from a field value."""
        out = []
        # First try linked targets
        links = extract_links(value)
        if links:
            for target, display in links:
                # use display name (more readable) but target is the canonical wiki page
                out.append((display, None))
        else:
            # No links: try splitting plaintext
            for v in split_multivalue(value):
                v = LINK_PATTERN.sub("", v).strip()
                if v and len(v) < 100:
                    out.append((v, None))
        return out

    src = updates["wikipedia_vi_url"]
    for fname, fval in fields.items():
        if fname in PARENT_FIELD:
            for name, qid in resolve_links_in_field(fval):
                pid2, _ = store.find_or_create(name)
                store.upsert_relation("parent_father", pid, pid2, source_ref=src)
                rel_count["father"] += 1
        elif fname in MOTHER_FIELD:
            for name, qid in resolve_links_in_field(fval):
                pid2, _ = store.find_or_create(name)
                store.upsert_relation("parent_mother", pid, pid2, source_ref=src)
                rel_count["mother"] += 1
        elif fname in SPOUSE_FIELD:
            for rank, (name, qid) in enumerate(resolve_links_in_field(fval), start=1):
                pid2, _ = store.find_or_create(name)
                store.upsert_relation("spouse", pid, pid2, rank=rank, source_ref=src)
                rel_count["spouse"] += 1
        elif fname in CHILD_FIELD:
            for name, qid in resolve_links_in_field(fval):
                if name.startswith("#") or "Gia quyến" in name or "Xem" in name:
                    rel_count["skipped"] += 1
                    continue
                pid2, _ = store.find_or_create(name)
                # Convention: parent_father from=child, to=parent.
                # canonical has child pid2 → relation: pid2 parent_father pid
                store.upsert_relation("parent_father", pid2, pid, source_ref=src)
                rel_count["child"] += 1
        elif fname in SIBLING_FIELD:
            for name, qid in resolve_links_in_field(fval):
                pid2, _ = store.find_or_create(name)
                store.upsert_relation("sibling_full", pid, pid2, source_ref=src)
                rel_count["sibling"] += 1

    if verbose:
        print(f"  [{title}] qid={page['qid']} {sum(rel_count.values())} relations: {rel_count}")
    return {"title": title, "found": True, "infobox": True,
            "qid": page["qid"], "person_id": str(pid),
            "relations": rel_count, "created": created}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--titles", type=Path, required=True,
                    help="newline-delimited list of Wikipedia VN titles")
    ap.add_argument("--delay", type=float, default=0.4,
                    help="seconds between requests (politeness)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    titles = [t.strip() for t in args.titles.read_text().splitlines() if t.strip() and not t.startswith("#")]
    print(f"importing {len(titles)} titles into {args.db}")

    con = duckdb.connect(str(args.db))
    store = Store(con)

    summary = {"found": 0, "infobox": 0, "missing": 0, "no_infobox": 0, "created": 0}
    rel_total = {"father": 0, "mother": 0, "spouse": 0, "child": 0, "sibling": 0, "skipped": 0}

    for i, title in enumerate(titles, 1):
        try:
            r = import_one(store, title, verbose=args.verbose)
        except Exception as e:
            print(f"[{i}/{len(titles)}] {title}: ERROR {e}", file=sys.stderr)
            continue

        if not r.get("found"):
            summary["missing"] += 1
            print(f"[{i}/{len(titles)}] {title}: missing")
        elif not r.get("infobox"):
            summary["no_infobox"] += 1
            print(f"[{i}/{len(titles)}] {title}: no infobox")
        else:
            summary["found"] += 1
            summary["infobox"] += 1
            if r.get("created"):
                summary["created"] += 1
            for k, v in r["relations"].items():
                rel_total[k] += v
            print(f"[{i}/{len(titles)}] {title}: ok rels={sum(r['relations'].values())}")

        time.sleep(args.delay)

    con.execute("CHECKPOINT")
    print()
    print(f"SUMMARY: {summary}")
    print(f"RELATIONS: {rel_total}")
    print(f"Total persons in DB: {con.execute('SELECT COUNT(*) FROM person').fetchone()[0]}")
    print(f"Total relations in DB: {con.execute('SELECT COUNT(*) FROM relation').fetchone()[0]}")


if __name__ == "__main__":
    main()
