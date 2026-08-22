"""`assert_snapshot.py` must fail for the thing it claims to check.

RUN AS A SUBPROCESS, every one of these. The script exists to be executed by
seven platforms out of a bare `actions/checkout`, with nothing installed and
this repository not on the path -- so importing it here and calling `main()`
would test a different program than the one that ships. It would also hide the
one defect most likely to occur: the `sys.path` insert being wrong.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

from contoso_product.expected import EXPECTED

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "assert_snapshot.py"


def run(snapshot: pathlib.Path, *extra: str, cwd: pathlib.Path | None = None):
    """The script, exactly as a platform runs it: no install, no PYTHONPATH.

    `-S` IS THE WHOLE POINT OF THIS HELPER. Without it the subprocess inherits
    pytest's virtualenv, where `contoso_product` is installed, so the script
    finds the package whatever its own `sys.path` does -- and the first draft of
    this file proved it: deleting the `sys.path.insert` the platforms depend on
    left all twelve tests green. `-S` drops site-packages, which is the CI
    runner's condition (`actions/checkout`, nothing built) rather than a
    developer's.
    """
    return subprocess.run(
        [sys.executable, "-S", str(SCRIPT), str(snapshot), *extra],
        capture_output=True,
        text=True,
        cwd=str(cwd or ROOT.parent),
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
    )


def write(tmp_path: pathlib.Path, snap: dict) -> pathlib.Path:
    p = tmp_path / "product_snapshot.json"
    p.write_text(json.dumps(snap, indent=2), encoding="utf-8")
    return p


def good() -> dict:
    """What a passing cell writes, plus the keys a real snapshot carries."""
    return {**EXPECTED, "contracts": ["a", "b"]}


def test_a_snapshot_carrying_the_figures_passes(tmp_path):
    got = run(write(tmp_path, good()))
    assert got.returncode == 0, got.stderr
    assert "carries the family's figures" in got.stdout
    # The figures are PRINTED, not merely approved. A green step that names no
    # number is the shape this whole exercise exists to replace.
    for value in EXPECTED.values():
        assert value in got.stdout


def test_a_wrong_number_fails_and_names_both_values(tmp_path):
    """THE NEGATIVE CONTROL. Mutate the DATA, not a docstring."""
    snap = good()
    snap["revenue_usd"] = "129341157.6800"
    got = run(write(tmp_path, snap))
    assert got.returncode == 1
    assert "129341157.6800" in got.stderr
    assert EXPECTED["revenue_usd"] in got.stderr


def test_every_disagreement_is_reported_in_one_run(tmp_path):
    """Being told about one figure and finding the next on the rerun is two
    cycles for one answer."""
    snap = {k: "1" for k in EXPECTED}
    got = run(write(tmp_path, snap))
    assert got.returncode == 1
    for key in EXPECTED:
        assert key in got.stderr


def test_an_absent_figure_is_a_complaint_not_a_skip(tmp_path):
    snap = good()
    del snap["sale_lines"]
    got = run(write(tmp_path, snap))
    assert got.returncode == 1
    assert "sale_lines" in got.stderr


def test_an_empty_snapshot_fails(tmp_path):
    """Two nothings compared equal is the defect one level up; here it is one
    nothing approved."""
    got = run(write(tmp_path, {}))
    assert got.returncode == 1


def test_a_missing_snapshot_fails_rather_than_skipping(tmp_path):
    """The condition the script exists to catch: a run that produced no numbers."""
    got = run(tmp_path / "never-written.json")
    assert got.returncode != 0
    assert "no snapshot at" in got.stderr


def test_a_snapshot_that_is_not_json_fails(tmp_path):
    p = tmp_path / "product_snapshot.json"
    p.write_text("<html>404</html>", encoding="utf-8")
    got = run(p)
    assert got.returncode != 0
    assert "not JSON" in got.stderr


def test_formatting_is_not_a_disagreement(tmp_path):
    """A cell writing `129341157.67` produced the right money. Compared as
    strings it would fail; compared as decimals it does not."""
    snap = good()
    snap["revenue_usd"] = "129341157.67"
    snap["sale_lines"] = int(EXPECTED["sale_lines"])
    got = run(write(tmp_path, snap))
    assert got.returncode == 0, got.stderr


def test_a_dialect_gap_is_explained_and_still_fails(tmp_path):
    """`compare_products` lets a named gap through; this does not. A cell that
    cannot build gold cannot assert gold's numbers -- but it says why."""
    got = run(write(tmp_path, {"dialect_gap": "no MERGE on this engine"}))
    assert got.returncode == 1
    assert "no MERGE on this engine" in got.stderr


def test_failed_contracts_are_surfaced_alongside_the_numbers(tmp_path):
    snap = good()
    snap["revenue_usd"] = "0"
    snap["contract_failures"] = [{"contract": "money_is_never_stored_as_float"}]
    got = run(write(tmp_path, snap))
    assert got.returncode == 1
    assert "money_is_never_stored_as_float" in got.stderr


def test_the_label_names_the_cell(tmp_path):
    got = run(write(tmp_path, good()), "--label", "snowflake-platform-tasks")
    assert got.returncode == 0, got.stderr
    assert "snowflake-platform-tasks" in got.stdout


def test_it_runs_from_a_bare_checkout_with_nothing_installed(tmp_path):
    """The claim the platforms depend on: no `uv sync`, no wheel, no PYTHONPATH.

    `run()` already strips the environment, so every test above asserts this
    too. It is stated once on its own so that a failure names the reason rather
    than looking like eleven unrelated breakages.
    """
    got = run(write(tmp_path, good()), cwd=tmp_path)
    assert got.returncode == 0, got.stderr
