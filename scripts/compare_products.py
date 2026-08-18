#!/usr/bin/env python3
"""Fail if two Contoso runtimes disagree on gold numbers or ODCS contracts.

Reads the JSON each consumer wrote:

    --fabric  catalog.json / gold snapshot from contoso-fabric-platform
    --databricks  the sibling's equivalent
    --snowflake   optional gold snapshot; a dialect_gap key is a named gap, not a silent pass
    --airflow     optional gold snapshot from airflow-fabric-platform


The proof is not two green logs. Same aggregates, same contract names.

AND NOT TWO NOTHINGS. Equality alone once passed on two snapshots reporting
revenue 0, lines 0 and an empty contracts list -- "fabric and databricks agree
on revenue_usd=0 contracts=[]", exit 0. Two runtimes that produced nothing
compare equal, so `empty()` refuses a snapshot that carries no evidence before
any comparison happens. A runtime that genuinely cannot build gold says so with
`dialect_gap`, which is a NAMED gap and still allowed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


KEYS = ("revenue_usd", "cancelled_revenue_usd", "sale_lines", "contracts")


def load(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"missing snapshot: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def empty(snap: dict) -> str | None:
    """Why this snapshot is no evidence, or None if it carries some.

    THE AGGREGATES ARE THE ONLY EVIDENCE. `contracts` is a glob of the shared
    gold project's tests/ directory, so it is fully populated whether or not
    that runtime ever built a row -- the databricks snapshot names five
    contracts beside three zeros. Counting it as evidence is how a snapshot of
    nothing looked like a snapshot of something.

    A single zero is a legitimate value; all three at once is a runtime that
    built no gold.
    """
    if snap.get("dialect_gap"):
        return None
    try:
        nums = [float(snap.get(k, 0) or 0) for k in KEYS[:3]]
    except (TypeError, ValueError):
        return "aggregates are not numbers"
    if any(nums):
        return None
    return ("revenue, cancelled revenue and sale lines are all 0 -- this "
            "runtime built no gold, and comparing it to another would be two "
            "absences agreeing (contracts are globbed from the shared project, "
            "so they are named either way)")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fabric", type=Path, required=True)
    p.add_argument("--databricks", type=Path, required=True)
    p.add_argument("--snowflake", type=Path, default=None)
    p.add_argument("--airflow", type=Path, default=None)
    args = p.parse_args()
    a, b = load(args.fabric), load(args.databricks)

    errs: list[str] = []
    for name, snap in (("fabric", a), ("databricks", b)):
        why = empty(snap)
        if why:
            errs.append(f"{name}: {why}")
    if errs:
        print("compare_products FAILED", file=sys.stderr)
        for e in errs:
            print(f"  {e}", file=sys.stderr)
        return 1

    for key in ("revenue_usd", "cancelled_revenue_usd", "sale_lines", "contracts"):
        if key not in a or key not in b:
            errs.append(f"both snapshots must carry {key!r}")
            continue
        if a[key] != b[key]:
            errs.append(f"{key}: fabric={a[key]!r} databricks={b[key]!r}")

    # Every OTHER runtime is compared against fabric the same way, and each is
    # optional: a family member that has not run is absent, not agreeing.
    for flag, path in (("snowflake", args.snowflake), ("airflow", args.airflow)):
        if not path:
            continue
        s = load(path)
        if s.get("dialect_gap"):
            print(f"compare_products: {flag} named dialect gap: {s['dialect_gap']}")
            continue
        why = empty(s)
        if why:
            errs.append(f"{flag}: {why}")
            continue
        for key in KEYS:
            if key not in s:
                errs.append(f"{flag} snapshot must carry {key!r}")
                continue
            if a[key] != s[key]:
                errs.append(f"{key}: fabric={a[key]!r} {flag}={s[key]!r}")

    if errs:
        print("compare_products FAILED", file=sys.stderr)
        for e in errs:
            print(f"  {e}", file=sys.stderr)
        return 1
    agreed = ["fabric", "databricks"]
    if args.snowflake:
        agreed.append("snowflake")
    if args.airflow:
        agreed.append("airflow")
    print(
        f"compare_products: {', '.join(agreed)} agree on "
        f"revenue_usd={a.get('revenue_usd')} contracts={a.get('contracts')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
