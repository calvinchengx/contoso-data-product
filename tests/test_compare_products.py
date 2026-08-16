"""compare_products treats a snowflake dialect_gap as a named gap."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "compare_products.py"


def _snap(path: Path, **extra):
    body = {
        "revenue_usd": "1",
        "cancelled_revenue_usd": "0",
        "sale_lines": "2",
        "contracts": ["a"],
    }
    body.update(extra)
    path.write_text(json.dumps(body), encoding="utf-8")


def test_snowflake_named_gap_does_not_fail(tmp_path):
    fabric = tmp_path / "f.json"
    dbx = tmp_path / "d.json"
    sf = tmp_path / "s.json"
    _snap(fabric)
    _snap(dbx)
    _snap(sf, dialect_gap="DuckDB has no QUALIFY", revenue_usd="0")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--fabric", str(fabric), "--databricks", str(dbx), "--snowflake", str(sf)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    assert "dialect gap" in r.stdout.lower()
