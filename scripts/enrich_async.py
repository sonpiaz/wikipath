#!/usr/bin/env python3
"""Async LLM enrichment — 10× throughput vs enrich_llm.py via asyncio.

Reads candidate list (qid + Wikipedia VN title) from JSON, fetches articles
concurrently, sends to Kyma deepseek-v4-pro, validates source_sentence,
writes to DuckDB. Semaphore caps concurrent in-flight LLM calls.

Improvements over enrich_llm.py:
  - asyncio + aiohttp, semaphore-bounded concurrency
  - max_tokens 4000 (was 2000 — fixes 20% JSON truncation rate)
  - JSON repair fallback: trim trailing junk then retry parse
  - candidate list driven by SPARQL (200 famous figures) not hand-typed
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import uuid
from pathlib import Path

import aiohttp
import duckdb

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "wikipath.duckdb"
NS = uuid.UUID("8b0e3c4f-1234-5000-8000-000000000000")
USER_AGENT = "wikipath-enrich-async/0.1 (https://github.com/sonpiaz/wikipath; sonpiaz@gmail.com)"
WIKI_API = "https://vi.wikipedia.org/w/api.php"
KYMA_API = "https://api.kymaapi.com/v1/chat/completions"
# Override via the LLM_MODEL env var. Default is the stable-tier DeepSeek v3
# (verified 100% success in `bench_models.py`). Use deepseek-v4-pro for higher
# quality when its preview tier is responsive; we found v4-pro intermittent
# under sustained load 2026-05-10.
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-v3")

SYMMETRIC_KINDS = {
    "spouse", "concubine",
    "sibling_full", "sibling_paternal", "sibling_maternal",
}


# ─────────── Name validation (forward guard against LLM false-positives) ───────────
#
# Pilot 200-batch (2026-05-10) surfaced 1.7% schema-level false positives where
# the LLM extracted generic phrases as person names ("6 anh chị em", "con trai
# cả", bare surnames like "Phan"). Faithful-to-source but invalid as identifiers.
# See SPEC §4.8.

GENERIC_NAME_PATTERN = re.compile(
    r"^(các |những |\d+\s)?"
    r"(anh chị em|vợ|chồng|con( trai| gái)?|cha|mẹ|cha mẹ|"
    r"các con|tổ tiên|hậu duệ|cháu|chắt|phu nhân|phu quân|"
    r"con cái|con trưởng|con thứ|con cả|con út|con nuôi|con riêng)\b",
    re.IGNORECASE,
)

# Leading honorifics to strip before validation. LLM occasionally prefixes
# "Vua Lý Thái Tổ" or "ông Nguyễn Trãi". Stripping preserves the real name.
HONORIFIC_PREFIX = re.compile(
    r"^(ông|bà|vua|hoàng đế|hoàng hậu|chúa|công chúa|hoàng tử|"
    r"thái tử|thái hậu|thái phi|đức|cụ|bác|chú|cô|dì|thầy)\s+",
    re.IGNORECASE,
)


def clean_person_name(raw: str | None) -> str | None:
    if not isinstance(raw, str):
        return None
    n = raw.strip()
    # Strip surrounding quotes/parens the LLM sometimes adds
    n = n.strip("\"'()[]{}«»“”‘’")
    # Strip leading honorifics (one pass; rare to stack)
    n = HONORIFIC_PREFIX.sub("", n).strip()
    return n or None


def is_valid_person_name(name: str | None) -> bool:
    """Reject generic phrases, digit-laden strings, bare surnames.

    Returns True iff `name` looks like a real Vietnamese person name.
    Designed to be precision-biased: prefer rejecting questionable input
    over admitting a generic phrase as a person identifier.
    """
    if not name:
        return False
    n = name.strip()
    if len(n) < 4:
        return False  # rejects "Phan", "Lê", bare surnames
    if re.search(r"\d", n):
        return False  # rejects "6 anh chị em", "3 con", "10 cháu"
    if GENERIC_NAME_PATTERN.search(n.lower()):
        return False
    if len(n.split()) < 2:
        return False  # VN names are 2-4 tokens; mononyms rejected (acceptable for v1)
    return True


def load_kyma_key() -> str:
    """Load the Kyma API key from the KYMA_API_KEY environment variable.

    The script optionally falls back to a .env file in the current working
    directory or the repo root for local dev convenience. Production /
    CI environments should set the env var directly.
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


# ─────────── UUID helpers (mirror seed_db.py) ───────────

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


# ─────────── Wikitext stripping (mirror enrich_llm.py) ───────────

def strip_wikitext(wt: str, max_chars: int = 3500) -> str:
    s = wt
    s = re.sub(r"<!--.*?-->", "", s, flags=re.DOTALL)
    s = re.sub(r"<ref[^>]*?/>", "", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.DOTALL)
    s = re.sub(r"\[\[(?:Tập tin|File|Image|Hình):[^\]]*?\]\]", "", s)

    def strip_templates(text: str) -> str:
        out = []
        i = 0
        while i < len(text):
            if text[i:i+2] == "{{":
                depth = 1
                j = i + 2
                while j < len(text) and depth > 0:
                    if text[j:j+2] == "{{":
                        depth += 1; j += 2
                    elif text[j:j+2] == "}}":
                        depth -= 1; j += 2
                    else:
                        j += 1
                i = j
            else:
                out.append(text[i]); i += 1
        return "".join(out)

    s = strip_templates(s)
    s = re.sub(r"\[\[([^\]|]+?)\|([^\]]+?)\]\]", r"\2", s)
    s = re.sub(r"\[\[([^\]]+?)\]\]", r"\1", s)
    s = re.sub(r"\[(?:https?|ftp)://[^\s]+\s+([^\]]+)\]", r"\1", s)
    s = re.sub(r"\[(?:https?|ftp)://[^\]]+\]", "", s)
    s = re.sub(r"'''([^']+)'''", r"\1", s)
    s = re.sub(r"''([^']+)''", r"\1", s)
    s = re.sub(r"==+\s*([^=\n]+?)\s*==+", r"\n\1\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()[:max_chars]


# ─────────── Async HTTP ───────────

async def fetch_wiki_page(session: aiohttp.ClientSession, title: str
                          ) -> tuple[str, str | None] | None:
    params = {
        "action": "query",
        "format": "json",
        "prop": "revisions|pageprops",
        "rvprop": "content",
        "rvslots": "main",
        "ppprop": "wikibase_item",
        "redirects": "1",
        "titles": title,
    }
    try:
        async with session.get(WIKI_API, params=params,
                               headers={"User-Agent": USER_AGENT},
                               timeout=aiohttp.ClientTimeout(total=30)) as resp:
            data = await resp.json()
    except Exception:
        return None
    pages = data.get("query", {}).get("pages", {})
    for pid, page in pages.items():
        if pid == "-1" or "missing" in page:
            return None
        revs = page.get("revisions", [])
        if not revs:
            return None
        return (revs[0]["slots"]["main"]["*"],
                page.get("pageprops", {}).get("wikibase_item"))
    return None


SYSTEM_PROMPT = """You are a careful Vietnamese-language structured-data
extractor. Given a Wikipedia article excerpt about a person, return strict
JSON conforming to the schema. Never invent facts. Every fact MUST include
a `source_sentence` that is a literal substring of the article text. If a
field is not stated, return null. Output JSON only — no prose, no markdown
fences."""

JSON_SCHEMA = """{
  "bio_short": "string ≤ 280 chars in Vietnamese",
  "bio_full": "string | null",
  "birth": {"year": int|null, "month": int|null, "day": int|null, "place": "string|null", "source_sentence": "literal|null"},
  "death": {"year": int|null, "month": int|null, "day": int|null, "place": "string|null", "source_sentence": "literal|null"},
  "family": {
    "father":  {"name": "string|null", "source_sentence": "literal|null"},
    "mother":  {"name": "string|null", "source_sentence": "literal|null"},
    "spouses":  [{"name": "string", "source_sentence": "literal"}],
    "children": [{"name": "string", "source_sentence": "literal"}],
    "siblings": [{"name": "string", "source_sentence": "literal"}]
  }
}"""


def repair_json(s: str) -> str | None:
    """Best-effort: trim trailing junk after last '}' then try again."""
    if not s:
        return None
    end = s.rfind("}")
    if end > 0:
        return s[: end + 1]
    return None


async def llm_extract(session: aiohttp.ClientSession, article: str, name: str,
                      key: str, retries: int = 2) -> dict | None:
    user = (
        f"Person: {name}\n\n"
        f"Article excerpt (Vietnamese):\n\"\"\"\n{article}\n\"\"\"\n\n"
        f"Schema:\n{JSON_SCHEMA}\n\n"
        "Rules:\n"
        "- Only include facts the article explicitly states.\n"
        "- source_sentence must be a literal substring of the article.\n"
        "- Family member names must be the full Vietnamese names from the article.\n"
        "- Skip generic phrases like 'vợ ông' or 'các con' without proper names.\n"
        "- Output strict JSON only.\n"
    )
    body = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
        "max_tokens": 4000,
        "response_format": {"type": "json_object"},
    }
    delay = 2.0
    for attempt in range(retries):
        try:
            async with session.post(
                KYMA_API,
                json=body,
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status == 429:
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                result = await resp.json()
                if resp.status >= 400 or "error" in result:
                    # Surface upstream errors (402 insufficient credits, 403
                    # unauthorized, 500 server error, etc.) instead of
                    # silently converting them into "llm parse fail".
                    err = result.get("error", {})
                    msg = err.get("message") if isinstance(err, dict) else str(err)
                    print(f"  LLM HTTP {resp.status}: {msg or result}",
                          file=sys.stderr, flush=True)
                    return None
            content = result["choices"][0]["message"]["content"]
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                repaired = repair_json(content)
                if repaired:
                    try:
                        return json.loads(repaired)
                    except json.JSONDecodeError:
                        pass
                # last attempt — give up
                if attempt == retries - 1:
                    return None
        except Exception:
            if attempt == retries - 1:
                return None
            await asyncio.sleep(delay)
            delay *= 2
    return None


# ─────────── Validation ───────────

def normalize_match(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def confidence_of(sent: str | None, article: str) -> int:
    if not sent or not isinstance(sent, str):
        return 40
    a = normalize_match(article)
    q = normalize_match(sent)
    if not q:
        return 40
    if q in a:
        return 90
    words = q.split()
    if len(words) >= 4:
        if " ".join(words[:4]) in a and " ".join(words[-4:]) in a:
            return 70
    return 50


# ─────────── DB (sync, called from main thread after async batch) ───────────

class Store:
    def __init__(self, con):
        self.con = con
        rows = con.execute(
            "SELECT id, wikidata_qid, birth_name FROM person"
        ).fetchall()
        self.qid_to_id = {r[1]: r[0] for r in rows if r[1]}
        self.name_to_id = {r[2]: r[0] for r in rows}

    def find_by_qid(self, qid):
        return self.qid_to_id.get(qid)

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

    def update_person(self, pid, fields):
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
        cols = ", ".join(f"{k} = COALESCE({k}, ?)"
                          if k.startswith(("birth_", "death_")) else f"{k} = ?"
                          for k in fields)
        args = list(fields.values()) + [pid]
        self.con.execute(
            f"UPDATE person SET {cols}, updated_at = CURRENT_TIMESTAMP "
            f"WHERE id = ?", args,
        )

    def upsert_relation(self, kind, from_id, to_id, *, source_ref, confidence):
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

async def fetch_and_extract(session, sem, cand, key):
    async with sem:
        page = await fetch_wiki_page(session, cand["title"])
        if not page:
            return {"cand": cand, "ok": False, "reason": "wiki missing"}
        wikitext, qid = page
        article = strip_wikitext(wikitext, 3500)
        if len(article) < 300:
            return {"cand": cand, "ok": False, "reason": "article too short",
                    "article": article}
        extracted = await llm_extract(session, article, cand["label"], key)
        if not extracted:
            return {"cand": cand, "ok": False, "reason": "llm parse fail"}
        return {"cand": cand, "ok": True, "qid": qid, "article": article,
                "extracted": extracted}


def apply_to_db(store: Store, result: dict, *, verbose: bool = False) -> dict:
    if not result.get("ok"):
        return {"rels": 0, "low_conf": 0, "bio_chars": 0}
    cand = result["cand"]
    article = result["article"]
    extracted = result["extracted"]
    qid = result["qid"] or cand["qid"]

    primary_id = store.find_by_qid(qid)
    if not primary_id and cand["label"] in store.name_to_id:
        primary_id = store.name_to_id[cand["label"]]
    if not primary_id:
        primary_id = store.find_or_stub(cand["label"])

    updates = {}
    bs = extracted.get("bio_short")
    if isinstance(bs, str) and bs.strip():
        updates["bio_short"] = bs.strip()[:280]
    bf = extracted.get("bio_full")
    if isinstance(bf, str) and bf.strip():
        updates["bio_full"] = bf.strip()
    if qid:
        updates["wikidata_qid"] = qid
    updates["wikipedia_vi_url"] = (
        f"https://vi.wikipedia.org/wiki/{urllib.parse.quote(cand['title'].replace(' ', '_'))}"
    )
    birth = extracted.get("birth") or {}
    death = extracted.get("death") or {}
    for src, prefix in [(birth, "birth"), (death, "death")]:
        for sf, dest in [("year", f"{prefix}_date_y"),
                         ("month", f"{prefix}_date_m"),
                         ("day", f"{prefix}_date_d"),
                         ("place", f"{prefix}_place")]:
            v = src.get(sf)
            if v:
                updates[dest] = v
    store.update_person(primary_id, updates)

    fam = extracted.get("family") or {}
    rels = 0
    low_conf = 0
    rejected = 0

    def resolve(name_raw):
        """Clean + validate + stub. Returns person uuid or None if invalid."""
        nonlocal rejected
        cleaned = clean_person_name(name_raw)
        if not is_valid_person_name(cleaned):
            rejected += 1
            return None
        return store.find_or_stub(cleaned)

    def add(kind, from_id, to_id, sent):
        nonlocal rels, low_conf
        if from_id is None or to_id is None:
            return
        conf = confidence_of(sent, article)
        if conf < 60:
            low_conf += 1
        ref = f"llm:{cand['title']}|{(sent or 'no-src')[:80]}"
        store.upsert_relation(kind, from_id, to_id,
                              source_ref=ref, confidence=conf)
        rels += 1

    if isinstance(fam.get("father"), dict) and fam["father"].get("name"):
        f = fam["father"]
        add("parent_father", primary_id, resolve(f["name"]),
            f.get("source_sentence"))
    if isinstance(fam.get("mother"), dict) and fam["mother"].get("name"):
        m = fam["mother"]
        add("parent_mother", primary_id, resolve(m["name"]),
            m.get("source_sentence"))
    for sp in fam.get("spouses") or []:
        if isinstance(sp, dict) and sp.get("name"):
            add("spouse", primary_id, resolve(sp["name"]),
                sp.get("source_sentence"))
    for ch in fam.get("children") or []:
        if isinstance(ch, dict) and ch.get("name"):
            add("parent_father", resolve(ch["name"]),
                primary_id, ch.get("source_sentence"))
    for sb in fam.get("siblings") or []:
        if isinstance(sb, dict) and sb.get("name"):
            add("sibling_full", primary_id, resolve(sb["name"]),
                sb.get("source_sentence"))
    return {"rels": rels, "low_conf": low_conf, "rejected": rejected,
            "bio_chars": len(updates.get("bio_short", ""))}


async def main_async(candidates, key, concurrency: int, store, checkpoint_every: int):
    """Stream LLM results into the DB as they complete.

    Crash-safe: writes happen incrementally with a CHECKPOINT every
    `checkpoint_every` successful results, so a SIGKILL mid-stream loses at
    most the last partial batch instead of the entire run.
    """
    sem = asyncio.Semaphore(concurrency)
    timeout = aiohttp.ClientTimeout(total=180)
    connector = aiohttp.TCPConnector(limit=concurrency * 2)
    totals = {"ok": 0, "fail": 0, "rels": 0, "low_conf": 0,
              "rejected": 0, "bio_chars": 0, "since_checkpoint": 0}
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        tasks = [fetch_and_extract(session, sem, c, key) for c in candidates]
        done = 0
        for coro in asyncio.as_completed(tasks):
            r = await coro
            done += 1
            cand = r["cand"]
            status = "✓" if r.get("ok") else "✗"
            print(f"[{done}/{len(candidates)}] {status} {cand['label']}"
                  f"{' (' + r.get('reason', '') + ')' if not r.get('ok') else ''}",
                  flush=True)
            if r.get("ok"):
                stats = apply_to_db(store, r)
                totals["ok"] += 1
                totals["rels"] += stats["rels"]
                totals["low_conf"] += stats["low_conf"]
                totals["rejected"] += stats.get("rejected", 0)
                totals["bio_chars"] += stats["bio_chars"]
                totals["since_checkpoint"] += 1
                if totals["since_checkpoint"] >= checkpoint_every:
                    store.con.execute("CHECKPOINT")
                    totals["since_checkpoint"] = 0
            else:
                totals["fail"] += 1
        # Final checkpoint for tail batch
        if totals["since_checkpoint"] > 0:
            store.con.execute("CHECKPOINT")
    return totals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--candidates", type=Path, required=True)
    ap.add_argument("--concurrency", type=int, default=10)
    ap.add_argument("--checkpoint-every", type=int, default=50,
                    help="commit + CHECKPOINT every N successful writes")
    args = ap.parse_args()

    candidates = json.loads(args.candidates.read_text())
    print(f"loaded {len(candidates)} candidates (model: {LLM_MODEL})")

    key = load_kyma_key()
    con = duckdb.connect(str(args.db))
    store = Store(con)
    init_persons = con.execute("SELECT COUNT(*) FROM person").fetchone()[0]
    init_rels = con.execute("SELECT COUNT(*) FROM relation").fetchone()[0]

    t0 = time.time()
    totals = asyncio.run(main_async(candidates, key, args.concurrency,
                                     store, args.checkpoint_every))
    total_t = time.time() - t0
    final_persons = con.execute("SELECT COUNT(*) FROM person").fetchone()[0]
    final_rels = con.execute("SELECT COUNT(*) FROM relation").fetchone()[0]

    print()
    print(f"SUMMARY: ok={totals['ok']} fail={totals['fail']} "
          f"in {total_t:.1f}s (~{total_t / max(1, totals['ok'] + totals['fail']):.1f}s/profile avg)")
    print(f"BIO ADDED: {totals['ok']} bios, "
          f"~{totals['bio_chars'] // max(1, totals['ok'])} chars avg")
    print(f"RELATIONS: +{totals['rels']} (low_conf flagged: {totals['low_conf']}, "
          f"name-rejected: {totals['rejected']})")
    print(f"PERSONS:   {init_persons} → {final_persons} (+{final_persons - init_persons})")
    print(f"RELS:      {init_rels} → {final_rels} (+{final_rels - init_rels})")


if __name__ == "__main__":
    main()
