#!/usr/bin/env python3
"""Temporal audit for `relation` table.

Flags edges that contradict biological possibility using birth/death years.
Skips any relation where the relevant year on either endpoint is NULL.

Direction convention (from internal/schema/001_init.sql):
  parent_father / parent_mother : from = child,  to = parent
  child_adopted/step/foster     : from = parent, to = child
  spouse / concubine            : symmetric
  sibling_*                     : symmetric

Outputs:
  scripts/audit_report.txt       human-readable summary + samples
  scripts/drop_bad_relations.sql DELETE statement Son will review

Read-only DB access. Does NOT mutate.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "wikipath.duckdb"
REPORT = ROOT / "scripts" / "audit_report.txt"
DROP_SQL = ROOT / "scripts" / "drop_bad_relations.sql"

# Tolerances
SPOUSE_GAP_MAX = 100   # years between one spouse's death and the other's birth
SIBLING_GAP_MAX = 60   # years between sibling birth years

# Known violation we expect to catch (HCM Q36014 + clone mother born 1995)
HCM_BAD_RELATION_ID = "fdc68360-e392-5466-99d5-2cb142a15f3d"


def fmt_years(by, dy):
    by_s = str(by) if by is not None else "?"
    dy_s = str(dy) if dy is not None else "?"
    return f"{by_s}-{dy_s}"


def run_rule(con, name, sql):
    """Run a rule, return (violations, count). Violations are tuples:
    (relation_id, kind, from_name, from_by, from_dy, to_name, to_by, to_dy, why)
    """
    rows = con.execute(sql).fetchall()
    return name, rows


# Each rule SELECT must return columns:
#   r_id, kind, from_name, from_by, from_dy, to_name, to_by, to_dy, why
RULES = [
    (
        "parent_born_after_child",
        # parent_*: from=child, to=parent. Parent's birth must be < child's birth.
        """
        SELECT r.id, r.kind,
               c.birth_name, c.birth_date_y, c.death_date_y,
               p.birth_name, p.birth_date_y, p.death_date_y,
               'parent born after child' AS why
        FROM relation r
        JOIN person c ON c.id = r.from_person_id
        JOIN person p ON p.id = r.to_person_id
        WHERE r.kind IN ('parent_father','parent_mother')
          AND c.birth_date_y IS NOT NULL
          AND p.birth_date_y IS NOT NULL
          AND p.birth_date_y > c.birth_date_y
        """,
    ),
    (
        "parent_died_before_child_born",
        # Parent died before child was conceived. Allow up to 1 yr (posthumous birth).
        """
        SELECT r.id, r.kind,
               c.birth_name, c.birth_date_y, c.death_date_y,
               p.birth_name, p.birth_date_y, p.death_date_y,
               'parent died >1y before child born' AS why
        FROM relation r
        JOIN person c ON c.id = r.from_person_id
        JOIN person p ON p.id = r.to_person_id
        WHERE r.kind IN ('parent_father','parent_mother')
          AND c.birth_date_y IS NOT NULL
          AND p.death_date_y IS NOT NULL
          AND p.death_date_y < c.birth_date_y - 1
        """,
    ),
    (
        "child_born_before_parent",
        # child_*: from=parent, to=child. Same logic, sides swapped.
        """
        SELECT r.id, r.kind,
               p.birth_name, p.birth_date_y, p.death_date_y,
               c.birth_name, c.birth_date_y, c.death_date_y,
               'child born before parent' AS why
        FROM relation r
        JOIN person p ON p.id = r.from_person_id
        JOIN person c ON c.id = r.to_person_id
        WHERE r.kind IN ('child_adopted','child_step','child_foster')
          AND p.birth_date_y IS NOT NULL
          AND c.birth_date_y IS NOT NULL
          AND c.birth_date_y < p.birth_date_y
        """,
    ),
    (
        "child_born_after_parent_death",
        """
        SELECT r.id, r.kind,
               p.birth_name, p.birth_date_y, p.death_date_y,
               c.birth_name, c.birth_date_y, c.death_date_y,
               'child born >1y after parent died' AS why
        FROM relation r
        JOIN person p ON p.id = r.from_person_id
        JOIN person c ON c.id = r.to_person_id
        WHERE r.kind IN ('child_adopted','child_step','child_foster')
          AND p.death_date_y IS NOT NULL
          AND c.birth_date_y IS NOT NULL
          AND c.birth_date_y > p.death_date_y + 1
        """,
    ),
    (
        "spouse_impossible_gap",
        # Either side dead long before the other was born.
        f"""
        SELECT r.id, r.kind,
               a.birth_name, a.birth_date_y, a.death_date_y,
               b.birth_name, b.birth_date_y, b.death_date_y,
               'spouse gap >{SPOUSE_GAP_MAX} yrs across death/birth' AS why
        FROM relation r
        JOIN person a ON a.id = r.from_person_id
        JOIN person b ON b.id = r.to_person_id
        WHERE r.kind IN ('spouse','concubine')
          AND a.birth_date_y IS NOT NULL
          AND b.birth_date_y IS NOT NULL
          AND (
            (a.death_date_y IS NOT NULL AND b.birth_date_y - a.death_date_y > {SPOUSE_GAP_MAX})
            OR
            (b.death_date_y IS NOT NULL AND a.birth_date_y - b.death_date_y > {SPOUSE_GAP_MAX})
          )
        """,
    ),
    (
        "sibling_birth_gap_too_large",
        f"""
        SELECT r.id, r.kind,
               a.birth_name, a.birth_date_y, a.death_date_y,
               b.birth_name, b.birth_date_y, b.death_date_y,
               'sibling birth gap >{SIBLING_GAP_MAX} yrs' AS why
        FROM relation r
        JOIN person a ON a.id = r.from_person_id
        JOIN person b ON b.id = r.to_person_id
        WHERE r.kind IN ('sibling_full','sibling_paternal','sibling_maternal')
          AND a.birth_date_y IS NOT NULL
          AND b.birth_date_y IS NOT NULL
          AND ABS(a.birth_date_y - b.birth_date_y) > {SIBLING_GAP_MAX}
        """,
    ),
]


def main():
    con = duckdb.connect(str(DB), read_only=True)

    all_bad_ids = set()
    rule_results = []  # list of (rule_name, rows)

    for rule_name, sql in RULES:
        rows = con.execute(sql).fetchall()
        rule_results.append((rule_name, rows))
        for r in rows:
            all_bad_ids.add(str(r[0]))

    hcm_caught = HCM_BAD_RELATION_ID in all_bad_ids

    # --- Write report ---
    lines = []
    lines.append("# wikipath relation temporal audit")
    lines.append(f"# DB: {DB}")
    lines.append("")
    lines.append("## Per-rule violation count")
    for rule_name, rows in rule_results:
        lines.append(f"  {rule_name:38s} {len(rows)}")
    lines.append("")
    lines.append(f"Total bad relations (unique ids): {len(all_bad_ids)}")
    lines.append(f"Known case caught (HCM + Hoang Thi Loan 1995): "
                 f"{'yes' if hcm_caught else 'no'}")
    lines.append("")

    for rule_name, rows in rule_results:
        lines.append("=" * 72)
        lines.append(f"Rule: {rule_name}  ({len(rows)} violations)")
        lines.append("=" * 72)
        for row in rows[:5]:
            (rid, kind,
             from_name, from_by, from_dy,
             to_name,   to_by,   to_dy, why) = row
            lines.append(
                f"  {from_name} ({fmt_years(from_by, from_dy)}) "
                f"--{kind}--> "
                f"{to_name} ({fmt_years(to_by, to_dy)})"
            )
            lines.append(f"    rel_id={rid}  why={why}")
        if len(rows) > 5:
            lines.append(f"  ... +{len(rows) - 5} more")
        lines.append("")

    REPORT.write_text("\n".join(lines), encoding="utf-8")

    # --- Write DROP sql (review-only, do NOT execute) ---
    sql_lines = []
    sql_lines.append("-- Generated by scripts/audit_relations.py")
    sql_lines.append("-- REVIEW BEFORE RUNNING. This deletes flagged relations.")
    sql_lines.append(f"-- {len(all_bad_ids)} relation rows targeted.")
    sql_lines.append(f"-- Known HCM case included: {'yes' if hcm_caught else 'no'}")
    sql_lines.append("")
    if all_bad_ids:
        ids_sorted = sorted(all_bad_ids)
        quoted = ",\n  ".join(f"'{rid}'" for rid in ids_sorted)
        sql_lines.append("BEGIN TRANSACTION;")
        sql_lines.append("DELETE FROM relation WHERE id IN (")
        sql_lines.append(f"  {quoted}")
        sql_lines.append(");")
        sql_lines.append("-- COMMIT;  -- uncomment after manual review")
        sql_lines.append("-- ROLLBACK;")
    else:
        sql_lines.append("-- No bad relations detected. Nothing to delete.")
    DROP_SQL.write_text("\n".join(sql_lines) + "\n", encoding="utf-8")

    # --- Stdout summary ---
    print(f"Report:    {REPORT}")
    print(f"Drop SQL:  {DROP_SQL}")
    print()
    for rule_name, rows in rule_results:
        print(f"  {rule_name:38s} {len(rows)}")
    print(f"  {'TOTAL UNIQUE BAD RELATIONS':38s} {len(all_bad_ids)}")
    print(f"  {'Known HCM case caught':38s} {'yes' if hcm_caught else 'NO'}")


if __name__ == "__main__":
    main()
