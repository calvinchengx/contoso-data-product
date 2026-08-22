#!/usr/bin/env python3
"""Fail if one cell's snapshot disagrees with the figures this repository publishes.

    scripts/assert_snapshot.py <path-to-product_snapshot.json>

WHY THIS EXISTS. Every platform in the family runs a nightly that proves its
pipeline RAN. None of them proved it produced the right answer: checked across
all seven platforms with an acceptance workflow, zero executed `compare_products`
and none compared a snapshot against an expected value. The pipelines write
`product_snapshot.json`; nothing read it back. A cell whose gold silently
returned different money would have stayed green indefinitely. That is G50, and
this script is the half of it that runs inside a single cell's own CI.

WHY IT IS NOT `compare_products.py`. That script diffs snapshots ACROSS cells and
therefore needs all of them at once, which no single platform's CI can have. This
one asks the question a cell can answer ALONE -- "are these the family's numbers?"
-- which is what a nightly needs. They are complements, not alternatives: this
catches a cell that drifted, `compare_products` catches a divergence between two
cells that are each internally consistent.

WHY IT LIVES HERE AND RUNS FROM A CHECKOUT. `EXPECTED` is core's to state (rule 1:
"the expected numbers exist only in this repository"), so a platform may not carry
a copy of either the figures or this logic -- seven copies of a comparison is seven
things to keep in step. A platform checks this repository out at a pinned ref and
runs this file; nothing is installed, nothing is pinned twice, and no leaf is
involved. Running it from the PRODUCT's virtualenv was the other candidate and was
rejected: no released wheel carries `expected.py` yet, so every cell would have
gone red until seven leaf pin-bump PRs merged.

WHAT IT DOES NOT CHECK, deliberately. Contract failures and dialect gaps are
`compare_products.py`'s business, and a cell that failed its own contracts has
already gone red in the step that ran them. This file is about the numbers. It
does report both when it finds them, because a snapshot that carries a
`dialect_gap` explains WHY its figures are missing and printing the complaint
without the reason wastes a cycle.

A MISSING SNAPSHOT IS A FAILURE, not a skip. The absence of the file is the exact
condition this exists to catch -- a run that produced no numbers at all, which is
indistinguishable from a green pipeline unless something says so.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

# The package, from this checkout rather than from an install. A platform runs
# this file straight out of `actions/checkout`, where nothing has been built.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from contoso_product.expected import EXPECTED, check  # noqa: E402


def load(path: pathlib.Path) -> dict:
    if not path.is_file():
        raise SystemExit(
            f"assert_snapshot FAILED: no snapshot at {path}\n"
            f"  The run produced no numbers to check. Either the pipeline did not "
            f"reach the step that publishes them, or it published them somewhere "
            f"else -- both are findings, and neither is a pass."
        )
    try:
        got = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"assert_snapshot FAILED: {path} is not JSON: {exc}") from exc
    if not isinstance(got, dict):
        raise SystemExit(
            f"assert_snapshot FAILED: {path} holds {type(got).__name__}, not an object"
        )
    return got


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("snapshot", type=pathlib.Path)
    p.add_argument(
        "--label",
        default="",
        help="the cell's name, so a log says which one this was",
    )
    args = p.parse_args()

    who = f"{args.label}: " if args.label else ""
    snap = load(args.snapshot)
    bad = check(snap)

    if not bad:
        # SAY WHAT WAS PROVED, not that nothing went wrong. "The build was green"
        # is compatible with the check never having run.
        print(f"assert_snapshot: {who}{args.snapshot} carries the family's figures")
        for key, want in EXPECTED.items():
            print(f"  {key} = {snap[key]}  (expected {want})")
        return 0

    print(f"assert_snapshot FAILED: {who}{args.snapshot}", file=sys.stderr)
    for line in bad:
        print(f"  {line}", file=sys.stderr)

    # The reason the figures are missing, when the snapshot states one. Not a
    # pass: a cell that cannot build gold cannot assert gold's numbers, and the
    # gap is what needs closing.
    if snap.get("dialect_gap"):
        print(f"\n  the snapshot names a dialect gap: {snap['dialect_gap']}", file=sys.stderr)
    failures = snap.get("contract_failures")
    if failures:
        names = ", ".join(
            f.get("contract", "?") if isinstance(f, dict) else str(f) for f in failures
        )
        print(f"  the snapshot also records failed contracts: {names}", file=sys.stderr)

    print(
        "\nThese are the figures every cell in the family must produce. A "
        "disagreement is either this cell's gold, or a change to the product "
        "that every other cell has yet to make.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
