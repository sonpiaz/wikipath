# wikipath data quality report

Generated: 2026-05-10T22:36:40
DB: `/Users/sonpiaz/wikipath/wikipath.duckdb`
Sample size per check: 1

## Totals

- Persons: **5,412**
- bio_short filled: 250 (4.6%)
- avatar_url filled: 1,358 (25.1%)
- Wikipedia VN URL: 237 (4.4%)
- Wikidata QID: 5,040 (93.1%)
- Relations: 1,335

## Quality checks

### `duplicate_pairs` — **29** record(s)

Same birth_name with birth year within ±2y. Likely double-entries from Wikidata vs Wikipedia VN import. Manual review before enrichment.

Samples:

```
{"a_id": "81d689c1-e19d-5741-ae05-6249bec212bd", "a_qid": "Q16156929", "b_id": "848cbcd7-ebae-515f-be71-71bd4c9c9c9b", "b_qid": "Q55568650", "name": "Chu Lai", "a_birth": 1946, "b_birth": 1946}
```

### `garbage_names` — **0** record(s)

Q-only ('Q12345'), year-only ('1949'), or too-short names. These are filtered at display time but still occupy enrichment slots.

### `nameless_no_source` — **0** record(s)

NULL birth_name AND no Wikipedia URL. LLM has nothing to ground on — DO NOT enrich these.

### `future_dates` — **0** record(s)

birth_date_y or death_date_y > 2026. Always wrong.

### `parent_child_age_gap` — **3** record(s)

Parent < 12y or > 60y older than child. Either wrong birth year or wrong relation.

Samples:

```
{"child_id": "9b3607a1-2270-5c8b-b1be-03716ba164f3", "parent_id": "4e8d1112-d198-57c5-8acd-ae1b5438121d", "child_name": "Tạ Duy Nhẫn", "parent_name": "Tạ Duy Hiển", "child_birth": 1954, "parent_birth": 1889, "gap": 65}
```

### `likely_dead_no_death_year` — **22** record(s)

Born before 1916 but no death_date_y. Almost certainly missing data, not still alive.

Samples:

```
{"id": "d5996101-821c-5fed-abc3-5744a37ab97e", "wikidata_qid": "Q1134494", "birth_name": "Dương Tam Kha", "birth_date_y": 901, "era": "pre-1500"}
```

### `isolated_nodes` — **4,563** record(s)

No relations on either side. Enriching adds bio but does NOT improve path-finding or tree exploration.

Samples:

```
{"id": "60b6062f-e29a-5ee7-9299-47cd9a17f133", "wikidata_qid": "Q237421", "birth_name": "Đặng Xuân Khu", "era": "1900-1950", "dynasty": "hien-dai"}
```

### `era_birth_mismatch` — **0** record(s)

Era bucket disagrees with birth_date_y. Cheap to repair, hurts display credibility.

### `self_relations` — **0** record(s)

X is related to X. Always wrong.

### `year_only_name` — **0** record(s)

Name is a 4-digit year like '1949'. Subset of garbage_names but called out separately for tracking the year-import regression.
