#!/usr/bin/env python3
"""Benchmark Kyma alternative models on the wikipath extraction task.

Runs the same SYSTEM_PROMPT + JSON_SCHEMA from enrich_async.py against N
Wikipedia VN articles for K candidate models, then scores each model on:
  - JSON validity rate (parses without repair)
  - JSON validity rate after repair
  - source_sentence literal-substring match rate
  - Total family-relations extracted (proxy for completeness)
  - Latency (median + p95)

Output: pretty-printed comparison table to stdout.

This script does NOT write to the database; safe to run while the bulk
enrichment is in progress.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.enrich_async import (
    SYSTEM_PROMPT, JSON_SCHEMA,
    fetch_wiki_page, strip_wikitext, repair_json,
    load_kyma_key, normalize_match,
)

KYMA_API = "https://api.kymaapi.com/v1/chat/completions"

# Default test bench — 5 Wikipedia VN article titles with varying structure
# (politicians + historic + cultural + scholar + diaspora) to stress
# different parts of the schema.
DEFAULT_TITLES = [
    "Nguyễn Du",           # pre-modern poet (rich infobox)
    "Trịnh Công Sơn",      # cultural icon
    "Lê Quý Đôn",          # pre-modern scholar
]

# Per-request hard timeout (asyncio.wait_for) — defends against the session
# timeout not firing on slow upstream models. 60s is comfortably above
# typical 5-30s extraction latency.
REQUEST_TIMEOUT_S = 60

# Models to bench. Format: (id, label, expected_avg_cost_per_1k_profiles_usd).
# Skipping preview-stage models (deepseek-v4-pro, deepseek-v4-flash) — they
# can hang on slow upstream; we still document them in DATA-SOURCES as the
# current production choice + a cost-optimized preview alternative.
DEFAULT_MODELS = [
    ("deepseek-v3",        "DeepSeek v3 (stable)",         0.80),
    ("gemini-2.5-flash",   "Gemini 2.5 Flash",             0.80),
    ("qwen-3.6-plus",      "Qwen 3.6 Plus",                1.20),
    ("glm-4.5-air",        "GLM 4.5 Air (cheap bulk)",     0.35),
]


async def call_model(
    session: aiohttp.ClientSession,
    model: str,
    article: str,
    name: str,
    key: str,
) -> tuple[float, dict | None, bool]:
    """Returns (elapsed_seconds, parsed_json or None, json_repaired_flag)."""
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
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
        "max_tokens": 4000,
        "response_format": {"type": "json_object"},
    }
    t0 = time.time()

    async def _post():
        async with session.post(
            KYMA_API,
            json=body,
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"},
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_S),
        ) as resp:
            return await resp.json()

    try:
        data = await asyncio.wait_for(_post(), timeout=REQUEST_TIMEOUT_S)
    except (asyncio.TimeoutError, Exception):
        return time.time() - t0, None, False

    elapsed = time.time() - t0
    if isinstance(data, dict) and "error" in data:
        err = data.get("error", {})
        msg = err.get("message") if isinstance(err, dict) else str(err)
        print(f"      ↳ HTTP error: {msg}", file=sys.stderr, flush=True)
        return elapsed, None, False
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return elapsed, None, False

    try:
        return elapsed, json.loads(content), False
    except json.JSONDecodeError:
        repaired = repair_json(content)
        if repaired:
            try:
                return elapsed, json.loads(repaired), True
            except json.JSONDecodeError:
                pass
    return elapsed, None, False


def count_relations(extracted: dict) -> int:
    fam = extracted.get("family") or {}
    n = 0
    if isinstance(fam.get("father"), dict) and fam["father"].get("name"):
        n += 1
    if isinstance(fam.get("mother"), dict) and fam["mother"].get("name"):
        n += 1
    for k in ("spouses", "children", "siblings"):
        for item in fam.get(k) or []:
            if isinstance(item, dict) and item.get("name"):
                n += 1
    return n


def count_substring_hits(extracted: dict, article: str) -> tuple[int, int]:
    """Returns (hits, total) for source_sentence literal-substring checks."""
    a = normalize_match(article)
    hits = 0
    total = 0
    fam = extracted.get("family") or {}
    def check(sent):
        nonlocal hits, total
        if isinstance(sent, str) and sent.strip():
            total += 1
            if normalize_match(sent) in a:
                hits += 1
    for k in ("father", "mother"):
        if isinstance(fam.get(k), dict):
            check(fam[k].get("source_sentence"))
    for k in ("spouses", "children", "siblings"):
        for item in fam.get(k) or []:
            if isinstance(item, dict):
                check(item.get("source_sentence"))
    for k in ("birth", "death"):
        v = extracted.get(k)
        if isinstance(v, dict):
            check(v.get("source_sentence"))
    return hits, total


async def main_async(titles, models, key):
    timeout = aiohttp.ClientTimeout(total=240)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        # Fetch articles once, reuse across models
        print(f"fetching {len(titles)} articles…", file=sys.stderr)
        articles = {}
        for title in titles:
            page = await fetch_wiki_page(session, title)
            if not page:
                print(f"  ✗ {title} (not found)", file=sys.stderr)
                continue
            wikitext, _qid = page
            articles[title] = strip_wikitext(wikitext, 3500)
            print(f"  ✓ {title} ({len(articles[title])} chars)", file=sys.stderr)

        # Run each model against each article
        results = {m_id: [] for m_id, _, _ in models}
        for m_id, m_label, _cost in models:
            print(f"\nmodel: {m_label}", file=sys.stderr)
            for title, article in articles.items():
                elapsed, extracted, repaired = await call_model(
                    session, m_id, article, title, key
                )
                if extracted is None:
                    results[m_id].append({
                        "title": title, "elapsed": elapsed,
                        "ok": False, "repaired": repaired,
                        "rels": 0, "src_hit": 0, "src_total": 0,
                    })
                    print(f"  {title:30s}  {elapsed:5.1f}s  FAIL", file=sys.stderr)
                else:
                    rels = count_relations(extracted)
                    hits, total = count_substring_hits(extracted, article)
                    results[m_id].append({
                        "title": title, "elapsed": elapsed,
                        "ok": True, "repaired": repaired,
                        "rels": rels, "src_hit": hits, "src_total": total,
                    })
                    flag = " (repaired)" if repaired else ""
                    print(f"  {title:30s}  {elapsed:5.1f}s  ok rels={rels} "
                          f"src={hits}/{total}{flag}", file=sys.stderr)

        return articles, results


def summarize(models, results):
    """Print one row per model with aggregate scores."""
    print()
    print(f"{'Model':32s} {'OK':>5s} {'Rep':>4s} {'Rels':>5s} {'Src%':>6s} "
          f"{'Med(s)':>7s} {'P95(s)':>7s}")
    print("-" * 80)
    for m_id, m_label, _cost in models:
        rs = results[m_id]
        ok_count = sum(1 for r in rs if r["ok"])
        rep_count = sum(1 for r in rs if r["repaired"])
        total_rels = sum(r["rels"] for r in rs)
        src_total = sum(r["src_total"] for r in rs)
        src_hit = sum(r["src_hit"] for r in rs)
        src_pct = (src_hit / src_total * 100) if src_total else 0.0
        elapsed = sorted(r["elapsed"] for r in rs if r["ok"])
        med = elapsed[len(elapsed) // 2] if elapsed else 0.0
        p95_i = int(len(elapsed) * 0.95)
        p95 = elapsed[p95_i - 1] if elapsed else 0.0
        print(f"{m_label[:32]:32s} {ok_count:>3d}/{len(rs):<1d} {rep_count:>4d} "
              f"{total_rels:>5d} {src_pct:>5.1f}% {med:>7.1f} {p95:>7.1f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--titles", nargs="+", default=None,
                    help="Wikipedia VN titles to test (default: 5 builtin)")
    ap.add_argument("--models", nargs="+", default=None,
                    help="Kyma model ids to test (default: 5 builtin)")
    args = ap.parse_args()

    titles = args.titles or DEFAULT_TITLES
    if args.models:
        models = [(m, m, 0.0) for m in args.models]
    else:
        models = DEFAULT_MODELS

    key = load_kyma_key()
    print(f"bench: {len(titles)} articles × {len(models)} models", file=sys.stderr)
    _, results = asyncio.run(main_async(titles, models, key))
    summarize(models, results)


if __name__ == "__main__":
    main()
