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


def test_a_runtime_that_built_nothing_is_not_agreement(tmp_path):
    """Two snapshots of nothing compared equal, and the tool said "agree".

    Measured before the guard existed: revenue 0, lines 0, contracts [] on both
    sides printed "fabric and databricks agree on revenue_usd=0 contracts=[]"
    and exited 0. The family's whole claim rests on this script, so an
    agreement between two absences is the worst thing it can report.
    """
    fabric = tmp_path / "f.json"
    dbx = tmp_path / "d.json"
    for p in (fabric, dbx):
        _snap(p, revenue_usd="0", cancelled_revenue_usd="0", sale_lines="0")
    r = subprocess.run([sys.executable, str(SCRIPT), "--fabric", str(fabric),
                        "--databricks", str(dbx)], capture_output=True, text=True)
    assert r.returncode == 1, r.stdout
    assert "built no gold" in r.stderr


def test_contracts_alone_are_not_evidence_a_runtime_ran(tmp_path):
    """`contracts` is globbed from the shared project, not produced by the run.

    The databricks snapshot carries five contract names beside three zeros, so
    treating a populated contracts list as evidence lets exactly that snapshot
    through -- which is what the first version of the guard did.
    """
    fabric = tmp_path / "f.json"
    dbx = tmp_path / "d.json"
    for p in (fabric, dbx):
        _snap(p, revenue_usd="0", cancelled_revenue_usd="0", sale_lines="0",
              contracts=["money_is_never_stored_as_float"])
    r = subprocess.run([sys.executable, str(SCRIPT), "--fabric", str(fabric),
                        "--databricks", str(dbx)], capture_output=True, text=True)
    assert r.returncode == 1, r.stdout


def test_airflow_is_compared_against_fabric_like_every_other_runtime(tmp_path):
    fabric = tmp_path / "f.json"
    dbx = tmp_path / "d.json"
    air = tmp_path / "a.json"
    _snap(fabric)
    _snap(dbx)
    _snap(air, revenue_usd="999")
    r = subprocess.run([sys.executable, str(SCRIPT), "--fabric", str(fabric),
                        "--databricks", str(dbx), "--airflow", str(air)],
                       capture_output=True, text=True)
    assert r.returncode == 1, r.stdout
    assert "airflow='999'" in r.stderr

    _snap(air)
    r = subprocess.run([sys.executable, str(SCRIPT), "--fabric", str(fabric),
                        "--databricks", str(dbx), "--airflow", str(air)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "airflow" in r.stdout
