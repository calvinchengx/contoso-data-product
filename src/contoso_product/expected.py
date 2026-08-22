"""The figures every cell must produce, as data rather than as prose.

WHY THIS FILE EXISTS. This repository is described as carrying "transforms,
contracts, expected numbers". The first two were in the package and the third
was PROSE: `129,341,157.6700` appeared in `docs/00-family.md` and in the plan,
and nowhere a program could read. So no cell could assert its own output
against the family's claim, and every witnessed figure in this family came from
a run somebody drove by hand. Six nightly acceptance runs proved a pipeline had
executed and none proved it produced the right answer (G50).

WHAT MAY GO IN HERE, AND WHAT MAY NOT. Only figures that are the SAME in every
cell. These three are properties of the seeded data and the gold models, so an
engine or an orchestrator that changes one of them has changed the product.

Gold ROW COUNTS are deliberately absent, and that is G42 rather than an
oversight: `fct_revenue_summary` returned 84 rows on two cells and 119 on
others, from identical data, because the seeded window sits inside a single
fiscal quarter and the group key includes the quarter. A run whose window
straddles a boundary produces roughly twice the groups. Publishing a row count
as an expectation would fail a correct cell for the calendar.

STRINGS, NOT FLOATS. A snapshot carries fixed-point strings, `"129341157.6700"`
with its trailing zeros, because money compared as a float is money compared
wrongly. `check()` compares the decimal VALUE so that a cell writing
`129341157.67` is not failed for the formatting, while `EXPECTED` keeps the
canonical spelling for anything rendering it.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

# The canonical spelling, exactly as a snapshot writes it.
EXPECTED: dict[str, str] = {
    "revenue_usd": "129341157.6700",
    "cancelled_revenue_usd": "2800504.4000",
    "sale_lines": "474044",
}


def check(snapshot: dict) -> list[str]:
    """Compare one cell's snapshot against the family's figures.

    Returns a list of complaints, empty when the snapshot agrees. A list rather
    than an exception so a caller can report every disagreement at once: being
    told about `revenue_usd` and then discovering `sale_lines` on the next run
    is two cycles for one answer.

    A MISSING KEY IS A COMPLAINT, not a skip. A snapshot that omits a figure
    cannot be said to agree with it, and the version of this that skipped
    absent keys would pass an empty snapshot -- the exact defect
    `compare_products.empty()` exists to prevent one level up.
    """
    bad: list[str] = []
    for key, want in EXPECTED.items():
        if key not in snapshot:
            bad.append(f"{key}: absent from the snapshot, expected {want}")
            continue
        got = snapshot[key]
        try:
            if Decimal(str(got)) != Decimal(want):
                bad.append(f"{key}: {got}, expected {want}")
        except (InvalidOperation, ValueError):
            bad.append(f"{key}: {got!r} is not a number, expected {want}")
    return bad
