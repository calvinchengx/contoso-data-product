"""The reading affordance has to be right, or it misleads instead of helping.

A generated inventory that silently falls behind the package is worse than no
inventory: a reader trusts it precisely because it looks generated.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from contoso_product import gold_dir, show, silver_dir


def test_the_inventory_is_read_from_the_package_not_declared():
    inventory = show.inventory()
    for layer, directory in (("silver", silver_dir()), ("gold", gold_dir())):
        on_disk = sorted(p.stem for p in (directory / "models").glob("*.sql"))
        assert inventory[layer]["models"] == on_disk, layer
        assert on_disk, f"{layer} has no models, so the lister is reading the wrong place"


def test_every_listed_file_exists_and_is_linked_at_the_installed_version():
    block = show.markdown()
    version = show.version()
    assert f"/blob/v{version}/" in block, "links must pin the version the reader installed"
    for layer, directory in (("silver", silver_dir()), ("gold", gold_dir())):
        for kind in ("models", "tests"):
            for path in (directory / kind).glob("*.sql"):
                assert f"`{path.stem}`" in block, f"{layer}/{kind}/{path.stem} is missing from the block"
                assert f"/{layer}/{kind}/{path.stem}.sql" in block


def test_models_and_tests_are_not_presented_as_pairs():
    """They have no correspondence, and a table implies one.

    The first draft put `silver_customers` in a row beside a test about orders.
    A reader would have believed that relationship.
    """
    block = show.markdown()
    assert "| model | test |" not in block


def test_staging_puts_the_real_sql_on_disk(tmp_path):
    where = show.stage(tmp_path / "product")
    staged = sorted(p.name for p in where.rglob("*.sql"))
    source = sorted(p.name for p in gold_dir().rglob("*.sql")) + sorted(
        p.name for p in silver_dir().rglob("*.sql")
    )
    assert staged == sorted(source)
    assert (where / "gold" / "dbt_project.yml").is_file()
    assert (where / "silver" / "dbt_project.yml").is_file()


def test_staging_replaces_a_stale_copy(tmp_path):
    """A previous run's file must not survive into the next one."""
    where = tmp_path / "product"
    show.stage(where)
    stale = where / "gold" / "models" / "a_model_that_was_deleted.sql"
    stale.write_text("select 1", encoding="utf-8")
    show.stage(where)
    assert not stale.exists(), "staging left a file the product no longer has"


def test_check_accepts_a_current_block_and_rejects_a_drifted_one(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# Leaf\n\n" + show.markdown() + "\n", encoding="utf-8")
    ok, message = show.check(readme)
    assert ok, message

    drifted = readme.read_text(encoding="utf-8").replace("dim_country", "dim_country_renamed", 1)
    readme.write_text(drifted, encoding="utf-8")
    ok, message = show.check(readme)
    assert not ok, "a drifted inventory was accepted"
    assert "Regenerate" in message


def test_check_says_what_to_do_when_there_is_no_block(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# Leaf\n", encoding="utf-8")
    ok, message = show.check(readme)
    assert not ok
    assert "--markdown" in message


def test_the_module_runs_as_a_command():
    """`make show-product` calls this, so the entry point is part of the contract."""
    done = subprocess.run(
        [sys.executable, "-m", "contoso_product.show"],
        capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent,
    )
    assert done.returncode == 0, done.stderr
    assert "contoso-data-product v" in done.stdout


def test_this_repository_s_own_readme_carries_a_current_inventory():
    """The core eats its own cooking.

    Seven leaves are about to embed this block. If the mechanism cannot keep
    one README right, it should not be shipped to seven.
    """
    readme = Path(__file__).resolve().parent.parent / "README.md"
    ok, message = show.check(readme)
    assert ok, message
