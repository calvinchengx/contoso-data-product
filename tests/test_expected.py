"""The published figures, and the prose that quotes them, must agree."""

from __future__ import annotations

import pathlib

from contoso_product.expected import EXPECTED, check

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_the_claim_quotes_what_the_package_publishes():
    """`docs/00-family.md` states the family's numbers. It may not drift.

    THE DOCUMENT IS NOT THE SOURCE ANY MORE, and this is the gate that makes
    that true rather than aspirational. Before `expected.py` the figures lived
    only in prose, in two files, maintained by hand -- the same shape as the
    matrix tables that shipped two wrong statuses and the policy inventory that
    was wrong 28 times in 70. A second copy is fine when something fails on
    disagreement; this is that something.

    Digit-grouping is normalised away because prose reads `129,341,157.6700`
    and a snapshot writes `129341157.6700`. What must match is the number.
    """
    claim = (ROOT / "docs" / "00-family.md").read_text(encoding="utf-8")
    plain = claim.replace(",", "")
    missing = [f"{k} = {v}" for k, v in EXPECTED.items()
               if k in claim and v not in plain]
    assert not missing, (
        "docs/00-family.md quotes a figure that no longer matches "
        "contoso_product.expected:\n  " + "\n  ".join(missing)
    )


def test_the_claim_quotes_at_least_one_of_them():
    """A guard for the guard above, which passes vacuously if the prose stops
    naming any figure at all -- a rename or a rewrite would silence it without
    anyone noticing the check had stopped checking."""
    claim = (ROOT / "docs" / "00-family.md").read_text(encoding="utf-8")
    assert any(k in claim for k in EXPECTED), (
        "docs/00-family.md names none of the published figures, so the "
        "agreement test above is asserting nothing"
    )


def test_row_counts_are_not_published():
    """G42: a gold row count is a function of WHEN a cell runs.

    `fct_revenue_summary` returned 84 on two cells and 119 on others from
    identical data, because the seeded window sits inside one fiscal quarter.
    Publishing one here would fail a correct cell for the calendar.
    """
    assert not [k for k in EXPECTED if "count" in k or k.endswith("_rows")], (
        "a row count reached EXPECTED; see G42 before adding one"
    )


def test_check_reports_every_disagreement_and_refuses_an_empty_snapshot():
    assert check(dict(EXPECTED)) == []
    # Reformatted but equal in value: the same number, not a failure.
    assert check({**EXPECTED, "revenue_usd": "129341157.67"}) == []
    assert len(check({})) == len(EXPECTED)
    assert len(check({**EXPECTED, "revenue_usd": "1", "sale_lines": "2"})) == 2
    assert check({**EXPECTED, "revenue_usd": "not a number"})
