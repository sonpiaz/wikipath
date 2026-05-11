# Takedown & Correction Requests

This page tells you how to ask wikipath to **fix, hide, or remove**
information about you or someone you represent.

## Quick path

**Email**: `sonxpiaz@gmail.com` (interim — will move to a dedicated
`takedown@` address before public launch).

**Subject line**: `wikipath takedown — <person name>` or
`wikipath correction — <person name>`.

**Include**:

1. The URL of the record (e.g. `https://wikipath.app/p/Q36014`) or the
   person's name + birth year if you can't find the URL.
2. What is wrong, or what needs to be removed, with a short explanation.
3. Your relationship to the subject (the subject themselves, family
   member, legal representative, journalist, etc.). For full removal of
   a living person, we may ask for verification.

## Response SLA

- **Initial acknowledgement**: within 3 days.
- **Action or substantive reply**: within 7 days.
- **Hard delete from the database**: within 30 days of confirmed removal
  request (soft delete is immediate; backups are purged on the 30-day
  cycle).

If we don't reply within 7 days, escalate by opening an issue at
https://github.com/start01/wikipath/issues with the label `takedown`.

## What we will do without push-back

- **Factual corrections** with a verifiable source (Wikipedia citation,
  book reference, journalist contact). We update the record + add the
  source.
- **Sensitive data scrubs** for living persons (contact info, addresses,
  ID numbers, photos of minors). Removed immediately.
- **Photograph removals** if the rights holder requests, regardless of
  the photographer.
- **Full record removal for living non-public-figures** who never gave
  consent. Removed immediately pending identity check.

## What we will discuss before acting

- **Removal of a public figure's record** (politician, celebrity,
  athlete, scholar). Public figures have a reduced privacy expectation
  for documented public activities. We will discuss scope — often the
  right answer is to scope what's documented rather than blanket removal.
- **Disputed facts about historic persons**. We prefer to record the
  dispute (multiple sources, different positions, lower confidence) over
  picking a winner. See [CODE-OF-CONDUCT.md](CODE-OF-CONDUCT.md).
- **Family tree edits requested by a relative**. We will ask for the
  relative's source for the edit, and may keep both versions with
  different `source_kind` rows.

## What we will not do

- Remove a true, well-sourced fact about a public figure's public
  activities solely because the subject does not like it.
- Remove an entire record of a historic / deceased person at the
  request of a non-heir.
- Forge edits to make records "more flattering" — see CODE-OF-CONDUCT.md.

## Vietnamese DMCA / copyright

For copyright takedowns (you believe a record reproduces your
copyrighted text or photograph without permission), please cite the
specific work and your rights basis. We follow procedures consistent
with Vietnamese Copyright Law (Luật Sở hữu trí tuệ 2005/2009/2019). The
project's compilation copyright is held under LICENSE-DATA; individual
upstream sources retain their own rights.

## Audit log

Every successful takedown or correction is logged in
`contribution_log` with the entity id, the kind of change, the
timestamp, and a redacted summary of the reason. The log is public
(Wikipedia-style history page per record) but personal data in the
removal request is not exposed.

## Last updated

2026-05-10.
