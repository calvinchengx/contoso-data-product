#!/usr/bin/env python3
"""Fail if two Contoso runtimes disagree on gold numbers or ODCS contracts.

Reads the JSON each consumer wrote:

    --fabric  catalog.json / gold snapshot from fabric-platform-notebook-pipelines
    --databricks  the sibling's equivalent
    --snowflake   optional gold snapshot; a dialect_gap key is a named gap, not a silent pass
    --airflow     optional gold snapshot from fabric-platform-airflow3
    --airflow-builtin  optional; from fabric-platform-airflow-builtin, where
                  the DAG runs inside Fabric's own Airflow rather than beside it
    --databricks-airflow  optional; from databricks-platform-airflow3 -- the
                  SAME engine and pins as --databricks with a different
                  orchestrator, so a disagreement between those two has exactly
                  one candidate explanation left


The proof is not two green logs. Same aggregates, same contract names.

AND NOT TWO NOTHINGS. Equality alone once passed on two snapshots reporting
revenue 0, lines 0 and an empty contracts list -- "fabric and databricks agree
on revenue_usd=0 contracts=[]", exit 0. Two runtimes that produced nothing
compare equal, so `empty()` refuses a snapshot that carries no evidence before
any comparison happens. A runtime that genuinely cannot build gold says so with
`dialect_gap`, which is a NAMED gap and still allowed.

AND A RUNTIME THAT FAILED ITS OWN CONTRACTS SAYS SO TOO, with
`contract_failures` -- and that is FATAL here, however well the numbers agree.

The reason it has to be fatal is the whole point of letting such a snapshot
exist at all. A cell used to refuse to publish anything when a contract failed,
which is correct in itself and removed that cell from this comparison entirely
-- so the family lost its evidence for a defect that was not the product's. The
answer was to separate RECORDING A MEASUREMENT from ASSERTING A PASS: the cell
writes what it measured and still exits non-zero, and the failure travels with
the evidence instead of being absent from it.

That separation only means anything while the assert still fails. If this
script reported "three runtimes agree", exited 0, and mentioned the failing
contract in passing, it would be publishing exactly the sentence the family
exists to prevent -- and the separation would have quietly become "publish
anyway" with extra JSON. So the aggregates are compared and reported as
normal, the failures are surfaced in full, and the exit code is non-zero.
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

    THE AGGREGATES ARE THE ONLY EVIDENCE. `contracts` was a glob of the shared
    gold project's tests/ directory, so it was fully populated whether or not
    that runtime ever built a row -- the databricks snapshot named five
    contracts beside three zeros. Counting it as evidence is how a snapshot of
    nothing looked like a snapshot of something.

    Some producers have since been fixed to name only the contracts they
    actually executed, which makes the field better evidence THERE and no
    better here: this script cannot tell which kind of snapshot it is holding,
    so it goes on treating the aggregates as the only evidence.

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


def contract_failures(snap: dict) -> list[dict]:
    """The contracts this runtime ran and failed, as it recorded them.

    ABSENT WHEN CLEAN, never `[]`. That distinction is load-bearing and the
    producing side is careful about it: absent means "this runtime checked and
    everything passed", where an empty list would be indistinguishable from a
    runtime that recorded the field without ever running a contract. `.get`
    with a default of `[]` reads both the same way, which is fine HERE -- this
    function only asks what failed -- but it is why nothing writes `[]`.
    """
    got = snap.get("contract_failures") or []
    return got if isinstance(got, list) else []


def describe_failure(f: dict) -> str:
    """One failing contract, in the producer's own words.

    `detail` comes verbatim from dbt's run_results.json rather than being
    reconstructed here, and `cause` is optional and platform-supplied: a
    platform knows its own emulator's defects and this script should not have
    to. Printing whatever arrived beats printing a shape this script imagined.
    """
    if not isinstance(f, dict):
        return f"  {f!r}"
    name = f.get("contract", "?")
    bits = [f"status={f.get('status', '?')}"]
    if f.get("failures") is not None:
        bits.append(f"failures={f['failures']}")
    line = f"  {name}: {', '.join(bits)}"
    if f.get("detail"):
        line += f"\n      {f['detail']}"
    if f.get("cause"):
        line += f"\n      cause: {f['cause']}"
    return line


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fabric", type=Path, required=True)
    p.add_argument("--databricks", type=Path, required=True)
    p.add_argument("--snowflake", type=Path, default=None)
    p.add_argument("--airflow", type=Path, default=None)
    p.add_argument("--airflow-builtin", type=Path, default=None)
    p.add_argument("--databricks-airflow", type=Path, default=None)
    args = p.parse_args()
    # ENUMERATED ONCE. The optional runtimes were listed in three separate
    # places -- the aggregate comparison, the agreement line and the contract
    # check -- so adding a family member meant remembering all three, and a
    # member added to two of them would be compared, reported as agreeing,
    # and never asked whether its contracts passed.
    optional = [
        ("snowflake", args.snowflake),
        ("airflow", args.airflow),
        ("airflow-builtin", args.airflow_builtin),
        ("databricks-airflow", args.databricks_airflow),
    ]
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
    for flag, path in optional:
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

    # THE AGGREGATES AGREE. Say so plainly -- that is a real result and it is
    # worth stating even when a contract failed, because "the numbers match and
    # a type contract does not" is a far more useful sentence than either half
    # alone. Then fail, below.
    agreed = ["fabric", "databricks"] + [f for f, path in optional if path]
    print(
        f"compare_products: {', '.join(agreed)} agree on "
        f"revenue_usd={a.get('revenue_usd')} contracts={a.get('contracts')}"
    )

    named = [("fabric", a), ("databricks", b)]
    for flag, path in optional:
        if path:
            named.append((flag, load(path)))
    failing = [(n, contract_failures(s)) for n, s in named if contract_failures(s)]
    if failing:
        print(
            "\ncompare_products FAILED: the numbers agree, but a runtime did "
            "not pass its own contracts.",
            file=sys.stderr,
        )
        for name, fails in failing:
            print(f"  {name}:", file=sys.stderr)
            for f in fails:
                print(describe_failure(f), file=sys.stderr)
        print(
            "\nAgreement on aggregates is not agreement that the product is "
            "correct. A contract is the part that says WHAT the numbers are, "
            "and one of these runtimes is reporting that its own answer to "
            "that is wrong.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
