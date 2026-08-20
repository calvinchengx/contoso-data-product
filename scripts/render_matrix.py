#!/usr/bin/env python3
"""Derive the README's matrix from the two documents that already state it.

WHY THIS EXISTS. The matrix was maintained by hand in three places and drifted:
on 2026-08-20 the README showed **two** green cells while `docs/01-plan.md`
recorded **five** green and two amber, with no red at all. Three cells were
drawn as not-started (`⬜`) over repositories carrying 8-16 commits and full
witnesses, and Snowflake · Tasks was drawn `🔴` where the plan says `🟡`. The
README pointed at the plan as the source of truth in the sentence directly above
the wrong table.

That is the same failure the ecosystem hub records against itself — "several
READMEs still say 'Reserved' over a tree carrying dozens of files, and trusting
that prose put two wrong statuses into this repo's first commit". Prose about
state goes stale; the fix is to stop writing it twice.

HOW IT JOINS, and why not on the cell name. `docs/00-family.md` holds the
LAYOUT (which repository sits in which row and column) and must not change;
`docs/01-plan.md` holds the STATUS and changes constantly. Their cell labels do
not match — the plan says "Fabric · notebooks + pipelines" where the family doc
says "product · engine-native" — so the join is on the PRODUCT REPOSITORY NAME,
which both carry verbatim. A renamed row or a new column therefore needs no edit
here, and a cell whose repo appears in neither file is reported rather than
silently drawn empty.

    scripts/render_matrix.py            # print the derived table
    scripts/render_matrix.py --check    # exit 1 if README.md disagrees
    scripts/render_matrix.py --write    # rewrite README.md's table in place
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAMILY = ROOT / "docs" / "00-family.md"
PLAN = ROOT / "docs" / "01-plan.md"
README = ROOT / "README.md"

# The status a cell gets when the layout names a repository the plan does not
# mention at all: not started, as distinct from started-and-failing.
UNKNOWN = "⬜"
NOT_APPLICABLE = "—"


def cells(row: str) -> list[str]:
    """The cells of one markdown table row, unpadded."""
    return [c.strip() for c in row.strip().strip("|").split("|")]


def layout(text: str) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """(columns, [(row label, [repo per column])]) from the family doc.

    Only `product · X` rows: the platform rows name the same cells from the
    other side, and including them would draw each status twice.
    """
    columns: list[str] = []
    rows: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        c = cells(line)
        if not columns and c[0] == "" and len(c) == 4:
            columns = c[1:]
            continue
        m = re.match(r"\*\*product · (.+?)\*\*", c[0])
        if m and len(c) == 4:
            rows.append((m.group(1), [x.strip("`") for x in c[1:]]))
    return columns, rows


def statuses(text: str) -> dict[str, str]:
    """{product repo: status glyph} from the plan's table."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        c = cells(line)
        if len(c) < 4 or c[0] in ("cell", "---"):
            continue
        product, status = c[1].strip("`"), c[3]
        # One glyph, and only the ones the matrix draws: an evidence column
        # full of prose must not be mistaken for a status.
        if product and status in ("✅", "🟡", "🔴", "⬜"):
            out[product] = status
    return out


def render(columns, rows, status) -> str:
    lines = ["|  | " + " | ".join(columns) + " |", "|---" * (len(columns) + 1) + "|"]
    for label, repos in rows:
        drawn = []
        for repo in repos:
            if repo == NOT_APPLICABLE:
                drawn.append(NOT_APPLICABLE)
            else:
                drawn.append(status.get(repo, UNKNOWN))
        lines.append(f"| **{label}** | " + " | ".join(drawn) + " |")
    return "\n".join(lines)


def readme_table(text: str) -> str | None:
    """The existing matrix block, found by its header rather than by line number."""
    m = re.search(r"^\|\s+\| Fabric \| Databricks \| Snowflake \|\n(?:\|.*\n)+", text, re.M)
    return m.group(0).rstrip("\n") if m else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    columns, rows = layout(FAMILY.read_text(encoding="utf-8"))
    if not columns or not rows:
        print("FAIL: parsed no matrix from docs/00-family.md — this check would be vacuous")
        return 2
    status = statuses(PLAN.read_text(encoding="utf-8"))
    if not status:
        print("FAIL: parsed no statuses from docs/01-plan.md — this check would be vacuous")
        return 2

    # Every repo the layout names should have a status. Reported, not assumed:
    # a silent UNKNOWN is how a built cell gets drawn as not-started.
    named = {r for _, repos in rows for r in repos if r != NOT_APPLICABLE}
    missing = sorted(named - set(status))
    derived = render(columns, rows, status)

    if args.write:
        text = README.read_text(encoding="utf-8")
        old = readme_table(text)
        if old is None:
            print("FAIL: no matrix found in README.md to replace")
            return 2
        README.write_text(text.replace(old, derived, 1), encoding="utf-8")
        print("README.md matrix rewritten from docs/01-plan.md")
    elif args.check:
        old = readme_table(README.read_text(encoding="utf-8"))
        if old is None:
            print("FAIL: no matrix found in README.md")
            return 1
        if old != derived:
            print("FAIL: README.md's matrix disagrees with docs/01-plan.md.\n")
            print("README says:\n" + old + "\n")
            print("the plan implies:\n" + derived + "\n")
            print("Run: scripts/render_matrix.py --write")
            return 1
        print(f"README matrix matches the plan ({len(named)} cells)")
    else:
        print(derived)

    if missing:
        print(f"\nNOTE: the layout names {len(missing)} repo(s) the plan does not: "
              + ", ".join(missing) + " — drawn as " + UNKNOWN)
    return 0


if __name__ == "__main__":
    sys.exit(main())
