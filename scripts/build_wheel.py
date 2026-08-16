#!/usr/bin/env python3
"""Build the contoso-data-product wheel and prove it works from the artifact.

A CHECKOUT IMPORT IS NOT A RELEASE. Consumers install this from a GitHub
Release, so what has to be proved is the built wheel, installed somewhere that
is not this source tree, in a process that cannot fall back to it.

THE GOLD PROJECT IS THE PART THAT BREAKS. `gold_dir()` returns a path inside
the installed package, and the dbt models, macros and tests only get there
because `[tool.setuptools.package-data]` says `gold/**/*`. Python code would
import perfectly with every .sql file missing, and the consumer would fail
later at `dbt run` with an empty project. So the probe counts the assets rather
than trusting that packaging did what it was told.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

# What the gold project must still contain once it has been through a wheel.
EXPECT_MODELS = 9
EXPECT_TESTS = 5


def declared_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version = "([^"]+)"', text, re.M)
    if not m:
        raise SystemExit("pyproject.toml has no version")
    return m.group(1)


def main() -> int:
    version = declared_version()
    tag = os.environ.get("GITHUB_REF_NAME", "").lstrip("v")
    if tag and tag != version:
        # Publishing v0.2.0 from a tree that says 0.1.0 produces a wheel whose
        # filename disagrees with the release it hangs under, and every
        # consumer URL is built from both.
        raise SystemExit(
            f"tag v{tag} does not match pyproject version {version}. "
            f"Bump the version in pyproject.toml, or tag v{version}."
        )

    shutil.rmtree(DIST, ignore_errors=True)
    subprocess.check_call(["uv", "build", "--wheel", "--out-dir", str(DIST), str(ROOT)])
    wheels = list(DIST.glob("contoso_data_product-*.whl"))
    if not wheels:
        raise SystemExit(f"no contoso_data_product wheel in {DIST}")

    # A THROWAWAY VENV, not this interpreter. Installed somewhere unrelated to
    # the source tree and run with cwd there, so an import that only worked
    # because the checkout was adjacent cannot pass. uv rather than pip: a
    # system interpreter is often externally managed and refuses outright.
    work = Path(tempfile.mkdtemp(prefix="contoso-product-wheel-"))
    venv = work / ".venv"
    subprocess.check_call(["uv", "venv", str(venv)])
    py = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.check_call(
        ["uv", "pip", "install", "--python", str(py), str(wheels[0])], cwd=work
    )
    probe = (
        "import pathlib, contoso_product as p;"
        "assert callable(p.run_bronze) and callable(p.run_silver);"
        "assert p.MONEY == 'decimal(19,4)', p.MONEY;"
        "g = pathlib.Path(p.gold_dir());"
        "assert g.is_dir(), g;"
        "assert (g / 'dbt_project.yml').is_file(), 'no dbt_project.yml in the wheel';"
        "m = sorted(x.name for x in (g / 'models').glob('*.sql'));"
        "t = sorted(x.name for x in (g / 'tests').glob('*.sql'));"
        "assert (g / 'macros' / 'flag.sql').is_file(), 'no macros in the wheel';"
        f"assert len(m) == {EXPECT_MODELS}, ('models', m);"
        f"assert len(t) == {EXPECT_TESTS}, ('tests', t);"
        "assert (g / 'models' / 'schema.yml').is_file(), 'no schema.yml in the wheel';"
        "import contoso_product.contracts as c;"
        "assert c.schema_yml().is_file(), 'contracts cannot read schema.yml';"
        "print('wheel ok:', len(m), 'models,', len(t), 'singular tests, contracts readable')"
    )
    subprocess.check_call([str(py), "-c", probe], cwd=work)
    print(f"built {wheels[0].name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
