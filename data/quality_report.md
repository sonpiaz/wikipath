# wikipath data quality report

Generated: 2026-05-10T22:31:14
DB: `/Users/sonpiaz/wikipath/wikipath.duckdb`
Sample size per check: 5

## Totals

- Persons: **6,027**
- bio_short filled: 254 (4.2%)
- avatar_url filled: 1,465 (24.3%)
- Wikipedia VN URL: 241 (4.0%)
- Wikidata QID: 5,633 (93.5%)
- Relations: 4,464

## Quality checks

### `duplicate_pairs` — **29** record(s)

Same birth_name with birth year within ±2y. Likely double-entries from Wikidata vs Wikipedia VN import. Manual review before enrichment.

Samples:

```
{"a_id": "81d689c1-e19d-5741-ae05-6249bec212bd", "a_qid": "Q16156929", "b_id": "848cbcd7-ebae-515f-be71-71bd4c9c9c9b", "b_qid": "Q55568650", "name": "Chu Lai", "a_birth": 1946, "b_birth": 1946}
{"a_id": "5857d2b2-53c9-5642-b2ae-3befaa5b3569", "a_qid": "Q22774325", "b_id": "61f3381b-916d-5201-91fe-fda639e1542e", "b_qid": "Q49055886", "name": "Diễm My", "a_birth": 1962, "b_birth": 1962}
{"a_id": "b1036b12-6460-51d1-8867-f31161e83db4", "a_qid": "Q30921217", "b_id": "c9f27c6c-69ea-5839-8b42-7204d99ebaa9", "b_qid": "Q118198776", "name": "Hồ Văn Cường", "a_birth": 2003, "b_birth": 2003}
{"a_id": "19175f3e-def8-5bbd-adc7-2b8f4df5f8d2", "a_qid": "Q466001", "b_id": "6e1aeb8a-f896-58f9-9779-6e70172c9803", "b_qid": "Q441057", "name": "Lê Duẩn", "a_birth": 1907, "b_birth": 1907}
{"a_id": "2f73c060-ad9d-5ee1-88b9-3a1c9440a7bf", "a_qid": "Q24957801", "b_id": "ba595ffd-a388-5499-8b38-54ba5e16eeb7", "b_qid": "Q131387901", "name": "Lê Tuấn Anh", "a_birth": 1968, "b_birth": 1970}
```

### `garbage_names` — **615** record(s)

Q-only ('Q12345'), year-only ('1949'), or too-short names. These are filtered at display time but still occupy enrichment slots.

Samples:

```
{"id": "900f142d-46a6-5baf-b80f-ecccb8e561b6", "wikidata_qid": null, "birth_name": "1936", "era": "1900-1950", "dynasty": null}
{"id": "3e7f4f92-c5ce-5e93-b16b-ed411951b685", "wikidata_qid": null, "birth_name": "2007", "era": "1900-1950", "dynasty": null}
{"id": "a86487ff-0833-5b83-b09a-fedf1e3b491d", "wikidata_qid": null, "birth_name": "1937", "era": "1900-1950", "dynasty": null}
{"id": "eb78f286-2141-54fa-95b2-a9e76b9c56f2", "wikidata_qid": null, "birth_name": "2021", "era": "1900-1950", "dynasty": null}
{"id": "1b330ab8-1e25-5c05-bf96-eb7f707c4e59", "wikidata_qid": null, "birth_name": "1938", "era": "1900-1950", "dynasty": null}
```

### `nameless_no_source` — **0** record(s)

NULL birth_name AND no Wikipedia URL. LLM has nothing to ground on — DO NOT enrich these.

### `future_dates` — **0** record(s)

birth_date_y or death_date_y > 2026. Always wrong.

### `parent_child_age_gap` — **3** record(s)

Parent < 12y or > 60y older than child. Either wrong birth year or wrong relation.

Samples:

```
{"child_id": "9b3607a1-2270-5c8b-b1be-03716ba164f3", "parent_id": "4e8d1112-d198-57c5-8acd-ae1b5438121d", "child_name": "Tạ Duy Nhẫn", "parent_name": "Tạ Duy Hiển", "child_birth": 1954, "parent_birth": 1889, "gap": 65}
{"child_id": "529915b1-6853-5699-9c10-ebfe41100af2", "parent_id": "74c9ac84-f3f5-56fb-9128-d78cd274c208", "child_name": "Mạc Mậu Hợp", "parent_name": "Mạc Tuyên Tông", "child_birth": 1560, "parent_birth": 1550, "gap": 10}
{"child_id": "d4a27a9a-ba7d-5945-88de-8147903b9316", "parent_id": "66c1fc3b-221b-56e2-a063-833a94390939", "child_name": "Thanh Vy", "parent_name": "Thanh Phong", "child_birth": 1947, "parent_birth": 1942, "gap": 5}
```

### `likely_dead_no_death_year` — **22** record(s)

Born before 1916 but no death_date_y. Almost certainly missing data, not still alive.

Samples:

```
{"id": "d5996101-821c-5fed-abc3-5744a37ab97e", "wikidata_qid": "Q1134494", "birth_name": "Dương Tam Kha", "birth_date_y": 901, "era": "pre-1500"}
{"id": "8872122f-c7a3-5ea7-85d7-fa30053c6a6a", "wikidata_qid": "Q702949", "birth_name": "Ngô Xương Xí", "birth_date_y": 945, "era": "pre-1500"}
{"id": "87ad1b3c-cb01-5f78-a2c9-aff1f74a0fea", "wikidata_qid": "Q10799084", "birth_name": "Nguyễn Dữ", "birth_date_y": 1500, "era": "1500-1900"}
{"id": "59229815-cf97-52b5-a993-22fd7c6232f2", "wikidata_qid": "Q16480780", "birth_name": "Cung Đình Quỳ", "birth_date_y": 1901, "era": "1900-1950"}
{"id": "245e5850-6546-5f10-971b-a9f42d93ea02", "wikidata_qid": "Q16480576", "birth_name": "Hoàng Tích Mịnh", "birth_date_y": 1904, "era": "1900-1950"}
```

### `isolated_nodes` — **4,415** record(s)

No relations on either side. Enriching adds bio but does NOT improve path-finding or tree exploration.

Samples:

```
{"id": "60b6062f-e29a-5ee7-9299-47cd9a17f133", "wikidata_qid": "Q237421", "birth_name": "Đặng Xuân Khu", "era": "1900-1950", "dynasty": "hien-dai"}
{"id": "6e1aeb8a-f896-58f9-9779-6e70172c9803", "wikidata_qid": "Q441057", "birth_name": "Lê Duẩn", "era": "1900-1950", "dynasty": "hien-dai"}
{"id": "746375f5-7c1c-5520-b6e6-c197bb4847b9", "wikidata_qid": "Q700943", "birth_name": "Nguyễn Văn Cúc", "era": "1900-1950", "dynasty": "hien-dai"}
{"id": "a9b3330d-efdc-5550-9882-5956c5bc825f", "wikidata_qid": "Q438999", "birth_name": "Nguyễn Duy Cống", "era": "1900-1950", "dynasty": "hien-dai"}
{"id": "33895f04-8048-5891-a3e4-ba54f9f8317d", "wikidata_qid": "Q380980", "birth_name": "Nông Đức Mạnh", "era": "1950+", "dynasty": "hien-dai"}
```

### `era_birth_mismatch` — **61** record(s)

Era bucket disagrees with birth_date_y. Cheap to repair, hurts display credibility.

Samples:

```
{"id": "bedef859-f791-5d7f-81d7-6e8dadd62f51", "wikidata_qid": "Q317055", "birth_name": "Nguyễn Phúc Bửu Đảo", "birth_date_y": 1885, "era": "1900-1950"}
{"id": "1d04c8b4-3f76-52e8-a979-2c262f4a9acf", "wikidata_qid": "Q3290275", "birth_name": "Nguyễn Sinh Sắc", "birth_date_y": 1862, "era": "1900-1950"}
{"id": "f7af7e78-24a8-5ddb-80f0-c7e663f1371e", "wikidata_qid": null, "birth_name": "Hoàng Thị Loan", "birth_date_y": 1868, "era": "1900-1950"}
{"id": "111c88be-42de-502a-8276-4dec49e46362", "wikidata_qid": null, "birth_name": "Nguyễn Thị Thanh", "birth_date_y": 1884, "era": "1900-1950"}
{"id": "93dc49e5-ee1a-5e59-8a02-60ed2910160c", "wikidata_qid": null, "birth_name": "Nguyễn Sinh Khiêm", "birth_date_y": 1888, "era": "1900-1950"}
```

### `self_relations` — **0** record(s)

X is related to X. Always wrong.

### `year_only_name` — **21** record(s)

Name is a 4-digit year like '1949'. Subset of garbage_names but called out separately for tracking the year-import regression.

Samples:

```
{"id": "900f142d-46a6-5baf-b80f-ecccb8e561b6", "wikidata_qid": null, "birth_name": "1936"}
{"id": "3e7f4f92-c5ce-5e93-b16b-ed411951b685", "wikidata_qid": null, "birth_name": "2007"}
{"id": "a86487ff-0833-5b83-b09a-fedf1e3b491d", "wikidata_qid": null, "birth_name": "1937"}
{"id": "eb78f286-2141-54fa-95b2-a9e76b9c56f2", "wikidata_qid": null, "birth_name": "2021"}
{"id": "1b330ab8-1e25-5c05-bf96-eb7f707c4e59", "wikidata_qid": null, "birth_name": "1938"}
```
