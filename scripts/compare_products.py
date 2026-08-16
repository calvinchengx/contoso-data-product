#!/usr/bin/env python3
"""Fail if two Contoso runtimes disagree on gold numbers or ODCS contracts.

Reads the JSON each consumer wrote:

    --fabric  catalog.json / gold snapshot from contoso-data-platform
    --databricks  the sibling's equivalent

The proof is not two green logs. Same aggregates, same contract names.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"missing snapshot: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fabric", type=Path, required=True)
    p.add_argument("--databricks", type=Path, required=True)
    args = p.parse_args()
    a, b = load(args.fabric), load(args.databricks)

    errs: list[str] = []
    for key in ("revenue_usd", "cancelled_revenue_usd", "sale_lines", "contracts"):
        if key not in a or key not in b:
            errs.append(f"both snapshots must carry {key!r}")
            continue
        if a[key] != b[key]:
            errs.append(f"{key}: fabric={a[key]!r} databricks={b[key]!r}")

    if errs:
        print("compare_products FAILED", file=sys.stderr)
        for e in errs:
            print(f"  {e}", file=sys.stderr)
        return 1
    print(
        "compare_products: fabric and databricks agree on "
        f"revenue_usd={a.get('revenue_usd')} contracts={a.get('contracts')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
