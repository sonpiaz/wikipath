# Privacy

_Last updated: 2026-05-10. Effective from public launch._

wikipath collects two distinct kinds of data. This page covers both.

## 1. About the persons in the database (the "subjects")

wikipath is a public reference for **Vietnamese family relationships** of
notable people. Most persons in the database are historic (kings, scholars,
artists) or are public figures (politicians, celebrities, athletes) whose
biographical and family information is already published in independent
sources such as Wikipedia and Wikidata.

### Living persons

- Default consent for any living person is `opt_out`. Their record is
  **not visible** to the public until either (a) the person is a
  documented public figure with information already in independent
  published sources, or (b) the person (or a legal representative) signs
  a consent form.
- For documented public figures we may default to `consent_status=public`
  but a takedown request is honored — see [TAKEDOWN.md](TAKEDOWN.md) and
  §3 below.

### Deceased persons

Deceased persons are public-by-default. Direct descendants may still
request edits or context additions through the same takedown / edit
channels.

### Right to be forgotten

- Subjects (or their estates / legal heirs) may request **full removal**
  of a record by emailing the takedown contact.
- Soft delete is immediate; hard delete (record purged from backups)
  completes within 30 days.

### What we do _not_ store about subjects

- Social Security numbers, ID card numbers (CCCD/CMND), passport numbers
- Phone numbers, residential addresses, GPS coordinates
- Financial details, medical history, religious affiliations beyond what
  is itself a documented public fact (e.g. "Buddhist monk" as a public
  role is OK; private confession is not)
- Photographs of minors

## 2. About visitors of this site (the "users")

wikipath captures minimal anonymous interaction data so we can prioritize
which person records to enrich next, and to surface trending people on
the landing page.

### What we store

| Field | Purpose | Retention |
|---|---|---|
| `session_id` | Random UUID generated in your browser's localStorage; lets us count distinct visitors without identifying you | 90 days raw, then aggregated |
| `event_type` | One of: page_view, search, modal_open, tree_expand, node_click, external_click | 90 days raw |
| `person_id` | Which person record the event targets | 90 days raw |
| `query` | Your search string, if the event is a `search` | 90 days raw, trimmed to 200 chars |
| `referrer` (host only) | Where the click came from, host portion only | 90 days raw |
| `user_agent_hash` | SHA1 of your browser User-Agent; not reversible | 90 days raw |
| `country` | 2-character ISO code from CF-IPCountry header | 90 days raw |

After 90 days, raw events are aggregated into per-person popularity
counts and the source events are hard-deleted.

### What we do _not_ store about users

- Your IP address (the country code is derived at request time and only
  the 2-char code is kept)
- Your full User-Agent string (only the SHA1 hash)
- Cookies for tracking purposes (the `session_id` lives in localStorage,
  not in a cookie, and is scoped to wikipath origin only)
- Email, name, location, or any account information (we have no accounts)
- Cross-site tracking pixels or third-party analytics SDKs of any kind

### Opt out

Open your browser developer console on wikipath and run:

```
localStorage.setItem('wikipath:no-track', '1')
```

From that moment on, all `track()` calls on this device are no-ops. A
footer link "Không theo dõi tôi" provides the same toggle once F8 ships.
You can also block the `/api/event` endpoint at the network level if you
prefer; no functionality breaks.

### Legal basis

- **GDPR**: legitimate interest (product analytics, no profiling, no
  ads, no third-party sharing).
- **Vietnamese PDPL (Decree 13/2023)**: data is non-personal in the
  sense of the decree (no identifier links to a natural person without
  the session_id which the user controls).

## 3. Contact

Privacy or takedown requests: see [TAKEDOWN.md](TAKEDOWN.md) for the
contact channel and the response SLA (7 days from email contact).
