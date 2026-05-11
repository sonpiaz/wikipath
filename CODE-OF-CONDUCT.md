# Code of Conduct

wikipath documents Vietnamese family relationships. Many of those people
are alive, many are politically sensitive, and most have living
descendants who may stumble across this site. We hold contributors to a
higher bar than a typical open-source project.

## The short version

- **Cite or stay quiet.** Every fact you add must trace back to a
  published source (Wikipedia, Wikidata, a book, a verifiable news
  article, an oral history with attribution). No memes, no rumors, no
  political agendas.
- **Living people deserve more protection than dead people.** When in
  doubt, opt them out.
- **Vietnamese cultural sensitivity is non-negotiable.** Đa thê, tên
  húy, hiệu, miếu hiệu, dòng họ, chi, đời are first-class concepts here
  — respect their conventions. Do not impose Western kinship terminology
  on Vietnamese records.
- **No harassment, no doxxing, no slurs.** Includes references to
  political affiliation, religion, sexual orientation, or ethnicity
  used as an insult.

## Specifically prohibited

- Posting private contact info of any living person.
- Posting photographs of minors.
- Adding records of private individuals (not public figures) without
  their consent.
- Editing records to advance a political narrative (e.g. inflating /
  deflating a person's role in historical events without sources).
- Sock-puppet contributions to manufacture "consensus" on disputed edits.
- Harassment in PRs, issues, or commit messages.

## Disputed records

Vietnamese history has plenty of disputed records — multiple wives ranked
differently across sources, contested parentage, debated death dates.
The wikipath way:

1. Record both/all positions in the `name` or `relation` tables with
   distinct `source_kind` rows.
2. Mark each with appropriate `confidence` (lower for contested).
3. Let the UI present the dispute, not erase it.

Do not "win" a disputed record by deleting the opposing source.

## Enforcement

The maintainer (Son Piaz) is the current sole moderator. Reports go to
the takedown contact (see TAKEDOWN.md). Sanctions, in increasing order:

1. Warning + edit revert.
2. Temporary suspension from contributing.
3. Permanent ban from contributing + IP/email blocklist.
4. Public commit-log revert with attribution to the violation.

Sanctions for the same person are public in the contribution audit log.

## Attribution

This Code of Conduct is original to wikipath but draws structural
inspiration from the Wikimedia Foundation's Universal Code of Conduct
and the Contributor Covenant 2.1. Both are excellent references.
