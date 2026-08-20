"""The README's matrix must agree with the plan, because a reader trusts it.

On 2026-08-20 it did not: the README drew two green cells where
`docs/01-plan.md` recorded five green and two amber, three built cells as
not-started, and one amber cell as red — in a README whose sentence directly
above the table points at that plan as the source of truth. Nobody was careless;
the same state was written by hand in two places, and one of them moved.

These tests are about the CHECKER as much as the README: a check that cannot
fail is the thing that let the drift last.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "render_matrix.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=ROOT
    )


def test_the_readme_matrix_matches_the_plan():
    r = run("--check")
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_check_fails_when_the_readme_drifts(tmp_path, monkeypatch):
    """Mutate the README and require a failure.

    Without this the green above proves only that the script exits 0, which a
    checker that reads nothing also does.
    """
    readme = ROOT / "README.md"
    original = readme.read_text(encoding="utf-8")
    try:
        readme.write_text(original.replace("| **Airflow 3** | ✅", "| **Airflow 3** | ⬜", 1),
                          encoding="utf-8")
        r = run("--check")
        assert r.returncode != 0, "a drifted README passed the check"
        assert "disagrees" in r.stdout
    finally:
        readme.write_text(original, encoding="utf-8")


def test_it_refuses_to_pass_vacuously(tmp_path):
    """A parse that finds nothing must FAIL, not report agreement.

    The failure mode this repo has already met elsewhere: a checker that matched
    zero rows ran green for its whole life.
    """
    import shutil

    sandbox = tmp_path / "repo"
    shutil.copytree(ROOT, sandbox, ignore=shutil.ignore_patterns(
        ".git", "__pycache__", "node_modules", ".venv", "dist", "build"))
    (sandbox / "docs" / "01-plan.md").write_text("# no table here\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(sandbox / "scripts" / "render_matrix.py"), "--check"],
                       capture_output=True, text=True, cwd=sandbox)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "vacuous" in r.stdout


def test_every_cell_in_the_layout_has_a_status():
    """A repo the layout names and the plan forgets is drawn as not-started.

    That is indistinguishable from a real ⬜, so the script reports it and this
    test keeps the report at zero.
    """
    r = run()
    assert r.returncode == 0, r.stdout + r.stderr
    assert "NOTE: the layout names" not in r.stdout, r.stdout
