#!/usr/bin/env python3
"""LLM-based enrichment for Wikipedia VN articles missing infobox structure.

For each title in the input list:
  1. Fetch wikitext from vi.wikipedia.org.
  2. Strip to ~3000 char plain-text intro.
  3. Send to Kyma deepseek-v4-pro asking for structured JSON:
       bio_short, bio_full, birth/death dates+places, family relations
       (each with source_sentence quoting the article).
  4. Validate source_sentence is a literal substring of the article body.
  5. Update person.bio_short / bio_full / dates / places.
  6. Insert family relations as source_kind='llm_enrich' with confidence
     based on source_sentence match quality.

Confidence < 60 → row marked but flagged for moderation
                  (currently still inserted; v0.2 will queue them).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
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
USER_AGENT = "wikipath-enrich/0.1 (https://github.com/start01/wikipath; sonpiaz@gmail.com)"
WIKI_API = "https://vi.wikipedia.org/w/api.php"
KYMA_API = "https://api.kymaapi.com/v1/chat/completions"
LLM_MODEL = "deepseek-v4-pro"

SYMMETRIC_KINDS = {
    "spouse", "concubine",
    "sibling_full", "sibling_paternal", "sibling_maternal",
}


def load_kyma_key() -> str:
    """Load the Kyma API key from the KYMA_API_KEY environment variable.

    Falls back to a .env file in cwd or repo root for local dev. Get a key
    at https://api.kymaapi.com/.
    """
    env = os.environ.get("KYMA_API_KEY")
    if env:
        return env
    for candidate in (Path(".env"), ROOT / ".env"):
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                if line.startswith("KYMA_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(
        "KYMA_API_KEY not set. Export it in your shell or place it in .env "
        "at the repo root. Get a key at https://api.kymaapi.com/"
    )


# ─────────── UUID helpers ───────────

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


# ─────────── HTTP helpers ───────────

def http_post_json(url: str, body: dict, headers: dict, retries: int = 3) -> dict:
    data = json.dumps(body).encode()
    delay = 2.0
    for attempt in range(retries):
        req = urllib.request.Request(
            url, data=data,
            headers={**headers, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except Exception as e:
            if attempt == retries - 1:
                raise
            print(f"  POST retry after {delay}s ({e})", file=sys.stderr)
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")


def fetch_wiki_page(title: str) -> tuple[str, str | None] | None:
    """Returns (wikitext, qid) or None on miss."""
    qs = urllib.parse.urlencode({
        "action": "query",
        "format": "json",
        "prop": "revisions|pageprops",
        "rvprop": "content",
        "rvslots": "main",
        "ppprop": "wikibase_item",
        "redirects": "1",
        "titles": title,
    })
    req = urllib.request.Request(
        f"{WIKI_API}?{qs}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    pages = data.get("query", {}).get("pages", {})
    for pid, page in pages.items():
        if pid == "-1" or "missing" in page:
            return None
        revs = page.get("revisions", [])
        if not revs:
            return None
        wt = revs[0]["slots"]["main"]["*"]
        qid = page.get("pageprops", {}).get("wikibase_item")
        return (wt, qid)
    return None


# ─────────── Wikitext → plain text ───────────

def strip_wikitext(wt: str, max_chars: int = 3500) -> str:
    """Strip refs, comments, templates, files, then collapse [[link|display]]
    to display, keep first ~3500 chars (lead section)."""
    s = wt
    # Drop comments
    s = re.sub(r"<!--.*?-->", "", s, flags=re.DOTALL)
    # Drop refs
    s = re.sub(r"<ref[^>]*?/>", "", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.DOTALL)
    # Drop file/image links: [[Tập tin:...]] or [[File:...]] (handle nested brackets simply)
    s = re.sub(r"\[\[(?:Tập tin|File|Image|Hình):[^\]]*?\]\]", "", s)
    # Drop infobox templates and similar (entire block from {{Thông tin or {{Infobox to matching }})
    def strip_top_templates(text: str) -> str:
        out = []
        i = 0
        while i < len(text):
            if text[i:i+2] == "{{":
                # find matching }} respecting nesting
                depth = 1
                j = i + 2
                while j < len(text) and depth > 0:
                    if text[j:j+2] == "{{":
                        depth += 1
                        j += 2
                    elif text[j:j+2] == "}}":
                        depth -= 1
                        j += 2
                    else:
                        j += 1
                # skip the whole template
                i = j
            else:
                out.append(text[i])
                i += 1
        return "".join(out)
    s = strip_top_templates(s)
    # [[Link|Display]] → Display ; [[Link]] → Link
    s = re.sub(r"\[\[([^\]|]+?)\|([^\]]+?)\]\]", r"\2", s)
    s = re.sub(r"\[\[([^\]]+?)\]\]", r"\1", s)
    # Drop external [url label]
    s = re.sub(r"\[(?:https?|ftp)://[^\s]+\s+([^\]]+)\]", r"\1", s)
    s = re.sub(r"\[(?:https?|ftp)://[^\]]+\]", "", s)
    # ''italic'' / '''bold''' → plain
    s = re.sub(r"'''([^']+)'''", r"\1", s)
    s = re.sub(r"''([^']+)''", r"\1", s)
    # Headings
    s = re.sub(r"==+\s*([^=\n]+?)\s*==+", r"\n\1\n", s)
    # HTML tags
    s = re.sub(r"<[^>]+>", "", s)
    # Collapse whitespace
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()[:max_chars]


# ─────────── LLM call ───────────

SYSTEM_PROMPT = """You are a careful Vietnamese-language structured-data
extractor. Given a Wikipedia article excerpt about a person, return strict
JSON conforming to the schema below. Never invent facts. Every fact MUST
include a `source_sentence` that is a literal substring of the article
text. If a field is not stated, return null. Output JSON only — no prose,
no markdown fences."""

JSON_SCHEMA_HINT = """{
  "bio_short": "string ≤ 280 chars summarizing who the person is in Vietnamese",
  "bio_full": "string, full markdown intro paragraph in Vietnamese (or null if same as bio_short)",
  "birth": {"year": int|null, "month": int|null, "day": int|null, "place": "string|null", "source_sentence": "literal quote|null"},
  "death": {"year": int|null, "month": int|null, "day": int|null, "place": "string|null", "source_sentence": "literal quote|null"},
  "family": {
    "father":  {"name": "string|null", "source_sentence": "literal quote|null"},
    "mother":  {"name": "string|null", "source_sentence": "literal quote|null"},
    "spouses": [{"name": "string", "source_sentence": "literal quote"}],
    "children": [{"name": "string", "source_sentence": "literal quote"}],
    "siblings": [{"name": "string", "source_sentence": "literal quote"}]
  }
}"""


def llm_extract(article_text: str, person_name: str, key: str) -> dict | None:
    user_prompt = f"""Person: {person_name}

Article excerpt (Vietnamese):
\"\"\"
{article_text}
\"\"\"

Schema:
{JSON_SCHEMA_HINT}

Rules:
- Only include a field if the article explicitly states it.
- For each fact, include a literal substring of the article as source_sentence.
- Family member names must be Vietnamese-formatted full names as written in the article.
- Skip generic phrases like "vợ ông" or "các con" without proper names.
- Output strict JSON, no markdown.
"""

    body = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 2000,
        "response_format": {"type": "json_object"},
    }
    try:
        result = http_post_json(KYMA_API, body, {"Authorization": f"Bearer {key}"})
    except Exception as e:
        print(f"  LLM error: {e}", file=sys.stderr)
        return None
    try:
        content = result["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:
        print(f"  parse error: {e}", file=sys.stderr)
        return None


# ─────────── Validation ───────────

def normalize_for_match(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def confidence_of(source_sentence: str | None, article: str) -> int:
    if not source_sentence or not isinstance(source_sentence, str):
        return 40  # no source = low confidence
    a = normalize_for_match(article)
    q = normalize_for_match(source_sentence)
    if not q:
        return 40
    if q in a:
        return 90  # exact substring match
    # Try partial: 70% of words present in order
    words = q.split()
    if len(words) >= 4:
        # Check if first 4 + last 4 words present
        head = " ".join(words[:4])
        tail = " ".join(words[-4:])
        if head in a and tail in a:
            return 70
    return 50  # source claims but no literal match


# ─────────── DB ───────────

class Store:
    def __init__(self, con: duckdb.DuckDBPyConnection):
        self.con = con
        rows = self.con.execute(
            "SELECT id, wikidata_qid, birth_name FROM person"
        ).fetchall()
        self.qid_to_id = {r[1]: r[0] for r in rows if r[1]}
        self.name_to_id = {r[2]: r[0] for r in rows}

    def find_or_stub(self, name: str) -> uuid.UUID:
        if name in self.name_to_id:
            return self.name_to_id[name]
        slug = slug_from_name(name)
        pid = slug_to_uuid(slug)
        existing = self.con.execute(
            "SELECT 1 FROM person WHERE id = ?", [pid]
        ).fetchone()
        if not existing:
            self.con.execute(
                """
                INSERT INTO person (id, birth_name, era, gender,
                                    historicity, trust_score, primary_source)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT (id) DO NOTHING
                """,
                [pid, name, "1900-1950", "unknown", "probable", 55, "llm_enrich"],
            )
        self.name_to_id[name] = pid
        return pid

    def update_person(self, pid: uuid.UUID, fields: dict):
        if not fields:
            return
        # Don't clobber existing non-null bio_short / bio_full
        existing = self.con.execute(
            "SELECT bio_short, bio_full FROM person WHERE id = ?", [pid]
        ).fetchone()
        if existing:
            if existing[0]:
                fields.pop("bio_short", None)
            if existing[1]:
                fields.pop("bio_full", None)
        if not fields:
            return
        cols = ", ".join(f"{k} = COALESCE({k}, ?)" if k.startswith(("birth_", "death_"))
                          else f"{k} = ?" for k in fields)
        args = list(fields.values())
        args.append(pid)
        self.con.execute(
            f"UPDATE person SET {cols}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            args,
        )

    def upsert_relation(self, kind: str, from_id, to_id, *,
                        source_ref: str, confidence: int):
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
                source_kind = CASE
                    WHEN relation.confidence < excluded.confidence THEN excluded.source_kind
                    ELSE relation.source_kind
                END,
                confidence = GREATEST(relation.confidence, excluded.confidence)
            """,
            [rid, from_id, to_id, kind, "llm_enrich", source_ref, confidence],
        )


# ─────────── Pipeline ───────────

def enrich_one(title: str, store: Store, key: str, *, verbose: bool = False) -> dict:
    page = fetch_wiki_page(title)
    if not page:
        return {"title": title, "ok": False, "reason": "wiki page missing"}
    wikitext, qid = page
    article = strip_wikitext(wikitext, max_chars=3500)
    if len(article) < 200:
        return {"title": title, "ok": False, "reason": "article too short"}

    # Resolve primary person
    primary_id = None
    if qid and qid in store.qid_to_id:
        primary_id = store.qid_to_id[qid]
    if not primary_id and title in store.name_to_id:
        primary_id = store.name_to_id[title]
    if not primary_id:
        primary_id = store.find_or_stub(title)

    extracted = llm_extract(article, title, key)
    if not extracted:
        return {"title": title, "ok": False, "reason": "llm parse failed"}

    # Update person
    updates = {}
    bio_short = extracted.get("bio_short")
    if isinstance(bio_short, str) and bio_short.strip():
        updates["bio_short"] = bio_short.strip()[:280]
    bio_full = extracted.get("bio_full")
    if isinstance(bio_full, str) and bio_full.strip():
        updates["bio_full"] = bio_full.strip()
    if qid:
        updates["wikidata_qid"] = qid
    updates["wikipedia_vi_url"] = (
        f"https://vi.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
    )

    birth = extracted.get("birth") or {}
    death = extracted.get("death") or {}
    if birth.get("year"): updates["birth_date_y"] = birth["year"]
    if birth.get("month"): updates["birth_date_m"] = birth["month"]
    if birth.get("day"): updates["birth_date_d"] = birth["day"]
    if birth.get("place"): updates["birth_place"] = birth["place"]
    if death.get("year"): updates["death_date_y"] = death["year"]
    if death.get("month"): updates["death_date_m"] = death["month"]
    if death.get("day"): updates["death_date_d"] = death["day"]
    if death.get("place"): updates["death_place"] = death["place"]

    store.update_person(primary_id, updates)

    # Family relations
    fam = extracted.get("family") or {}
    rels_added = {"father": 0, "mother": 0, "spouse": 0, "child": 0, "sibling": 0}
    rels_low_conf = 0

    def add_relation(kind: str, from_id, to_id, src_sentence, label_key):
        nonlocal rels_low_conf
        conf = confidence_of(src_sentence, article)
        if conf < 60:
            rels_low_conf += 1
        ref = f"llm:{title}|{src_sentence[:80] if src_sentence else 'no-src'}"
        store.upsert_relation(kind, from_id, to_id,
                              source_ref=ref, confidence=conf)
        rels_added[label_key] += 1

    # father
    f = fam.get("father") or {}
    if isinstance(f, dict) and f.get("name"):
        target = store.find_or_stub(f["name"].strip())
        # primary has parent_father target
        add_relation("parent_father", primary_id, target, f.get("source_sentence"), "father")
    # mother
    m = fam.get("mother") or {}
    if isinstance(m, dict) and m.get("name"):
        target = store.find_or_stub(m["name"].strip())
        add_relation("parent_mother", primary_id, target, m.get("source_sentence"), "mother")
    # spouses
    for sp in fam.get("spouses") or []:
        if isinstance(sp, dict) and sp.get("name"):
            target = store.find_or_stub(sp["name"].strip())
            add_relation("spouse", primary_id, target, sp.get("source_sentence"), "spouse")
    # children
    for ch in fam.get("children") or []:
        if isinstance(ch, dict) and ch.get("name"):
            target = store.find_or_stub(ch["name"].strip())
            # convention: from=child, to=parent
            add_relation("parent_father", target, primary_id, ch.get("source_sentence"), "child")
    # siblings
    for sb in fam.get("siblings") or []:
        if isinstance(sb, dict) and sb.get("name"):
            target = store.find_or_stub(sb["name"].strip())
            add_relation("sibling_full", primary_id, target, sb.get("source_sentence"), "sibling")

    if verbose:
        print(f"  bio_short: {updates.get('bio_short', '<unchanged>')[:100]}", file=sys.stderr)
        print(f"  rels: {rels_added} (low_conf: {rels_low_conf})", file=sys.stderr)

    return {
        "title": title, "ok": True, "qid": qid,
        "rels": rels_added, "low_conf": rels_low_conf,
        "bio_chars": len(updates.get("bio_short", "")),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--titles", type=Path, required=True)
    ap.add_argument("--delay", type=float, default=0.6)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    titles = [t.strip() for t in args.titles.read_text().splitlines()
              if t.strip() and not t.startswith("#")]
    print(f"enriching {len(titles)} titles with {LLM_MODEL}")

    key = load_kyma_key()
    con = duckdb.connect(str(args.db))
    store = Store(con)

    initial_persons = con.execute("SELECT COUNT(*) FROM person").fetchone()[0]
    initial_relations = con.execute("SELECT COUNT(*) FROM relation").fetchone()[0]

    summary = {"ok": 0, "fail": 0}
    rel_total = {"father": 0, "mother": 0, "spouse": 0, "child": 0, "sibling": 0}
    bio_total = 0
    low_conf_total = 0

    for i, title in enumerate(titles, 1):
        print(f"[{i}/{len(titles)}] {title}…")
        try:
            r = enrich_one(title, store, key, verbose=args.verbose)
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            summary["fail"] += 1
            continue
        if r.get("ok"):
            summary["ok"] += 1
            for k, v in r["rels"].items():
                rel_total[k] += v
            bio_total += r["bio_chars"]
            low_conf_total += r["low_conf"]
            print(f"  ✓ {sum(r['rels'].values())} rels, {r['bio_chars']} bio chars, "
                  f"{r['low_conf']} low-conf")
        else:
            summary["fail"] += 1
            print(f"  ✗ {r.get('reason')}")
        con.execute("CHECKPOINT")
        time.sleep(args.delay)

    final_persons = con.execute("SELECT COUNT(*) FROM person").fetchone()[0]
    final_relations = con.execute("SELECT COUNT(*) FROM relation").fetchone()[0]
    print()
    print(f"SUMMARY: ok={summary['ok']} fail={summary['fail']}")
    print(f"RELATIONS: {rel_total}  (low_conf flagged: {low_conf_total})")
    print(f"PERSONS:   {initial_persons} → {final_persons} (+{final_persons - initial_persons})")
    print(f"RELATIONS: {initial_relations} → {final_relations} (+{final_relations - initial_relations})")


if __name__ == "__main__":
    main()
