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


def test_contract_failures_are_fatal_however_well_the_numbers_agree(tmp_path):
    """The exit code is what keeps option 4 from becoming "publish anyway".

    A cell may now record a measurement whose contracts failed, because
    refusing to publish removed that cell from the comparison the family
    exists to make. That separation -- recording a measurement vs asserting a
    pass -- only means something while the assert still fails. If this script
    reported agreement, exited 0, and mentioned the failing contract in
    passing, it would publish the exact sentence the family exists to prevent.
    """
    fabric, dbx = tmp_path / "f.json", tmp_path / "d.json"
    _snap(fabric)
    _snap(dbx, contract_failures=[{
        "contract": "money_is_never_stored_as_float", "status": "fail",
        "failures": 12, "detail": "Got 12 results, configured to fail if != 0",
        "cause": "databricks-emulator#46"}])
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--fabric", str(fabric), "--databricks", str(dbx)],
        cwd=ROOT, capture_output=True, text=True, check=False)
    assert r.returncode == 1, (r.stdout, r.stderr)
    # The agreement is still REPORTED -- "the numbers match and a type contract
    # does not" is more useful than either half alone.
    assert "agree on" in r.stdout, r.stdout
    # And the failure is surfaced in the producer's own words, cause included.
    assert "money_is_never_stored_as_float" in r.stderr
    assert "failures=12" in r.stderr
    assert "Got 12 results" in r.stderr
    assert "databricks-emulator#46" in r.stderr


def test_absent_contract_failures_is_not_the_same_as_empty(tmp_path):
    """Absent means "checked, all passed". `[]` must never be written.

    The producing side is careful about it because an empty list is
    indistinguishable from a runtime that recorded the field without ever
    running a contract. This asserts the consuming side treats a clean snapshot
    as clean -- and, by exercising `[]` too, that a runtime which somehow wrote
    one is not reported as failing.
    """
    fabric, dbx = tmp_path / "f.json", tmp_path / "d.json"
    _snap(fabric)
    _snap(dbx)
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--fabric", str(fabric), "--databricks", str(dbx)],
        cwd=ROOT, capture_output=True, text=True, check=False)
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "did not pass its own contracts" not in r.stderr

    _snap(dbx, contract_failures=[])
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--fabric", str(fabric), "--databricks", str(dbx)],
        cwd=ROOT, capture_output=True, text=True, check=False)
    assert r.returncode == 0, (r.stdout, r.stderr)


def test_a_failure_in_an_optional_runtime_is_fatal_too(tmp_path):
    """Snowflake and airflow are optional ARGUMENTS, not optional evidence.

    A snapshot that was passed in has to be held to the same rule; otherwise
    the way to make a contract failure disappear is to pass it as `--airflow`.
    """
    fabric, dbx, air = tmp_path / "f.json", tmp_path / "d.json", tmp_path / "a.json"
    _snap(fabric)
    _snap(dbx)
    _snap(air, contract_failures=[{"contract": "revenue_summary_loses_no_revenue",
                                   "status": "fail", "failures": 1}])
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--fabric", str(fabric), "--databricks", str(dbx),
         "--airflow", str(air)],
        cwd=ROOT, capture_output=True, text=True, check=False)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "airflow" in r.stderr and "revenue_summary_loses_no_revenue" in r.stderr
