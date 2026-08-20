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
    for layer, directory in ((inventory["silver"], silver_dir()), (inventory["gold"], gold_dir())):
        on_disk = sorted(p.stem for p in (directory / "models").glob("*.sql"))
        assert layer["models"] == on_disk
        assert on_disk, "a layer has no models, so the lister is reading the wrong place"


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


def test_check_pin_compares_against_the_release_not_the_package(monkeypatch):
    """A stale leaf must not be able to declare itself current.

    `version()` reports what the leaf installed, which IS its pin, so a check
    that compared the package to itself would pass on every leaf however far
    behind it was. The authority is the newest release.
    """
    monkeypatch.setattr(show, "version", lambda: "0.1.0")
    monkeypatch.setattr(show, "latest_release", lambda timeout=10.0: "0.5.0")
    ok, message = show.check_pin()
    assert not ok
    assert "v0.1.0" in message and "v0.5.0" in message

    monkeypatch.setattr(show, "version", lambda: "0.5.0")
    ok, message = show.check_pin()
    assert ok, message


def test_an_unreachable_release_api_fails_rather_than_skips(monkeypatch):
    """Skipping is how a check becomes decoration.

    A leaf installs this package from a GitHub release, so a leaf that cannot
    reach GitHub cannot resolve its dependencies either. Reporting that as a
    pass would leave the pin unchecked exactly when nobody could tell.
    """
    def unreachable(timeout=10.0):
        raise OSError("no route to host")

    monkeypatch.setattr(show, "latest_release", unreachable)
    ok, message = show.check_pin()
    assert not ok
    assert "network" in message


def test_the_bump_script_moves_both_pin_forms():
    """Two forms are in use, and rewriting only one would skip leaves silently.

    Five leaves pin a release wheel URL and one pins a git tag. A regex written
    for whichever form the author had in front of them is exactly how a leaf
    gets left behind while the sweep reports success.
    """
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "bump_leaves", Path(__file__).resolve().parent.parent / "scripts" / "bump_leaves.py"
    )
    assert spec is not None and spec.loader is not None, "bump_leaves.py is not importable"
    bump = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bump)

    wheel = (
        'contoso-data-product = { url = "https://github.com/calvinchengx/contoso-data-product'
        '/releases/download/v0.1.6/contoso_data_product-0.1.6-py3-none-any.whl" }'
    )
    moved = bump.repin(wheel, "0.5.0")
    assert "v0.5.0/contoso_data_product-0.5.0-py3-none-any.whl" in moved
    assert "0.1.6" not in moved

    tag = (
        'contoso-data-product = { git = "https://github.com/calvinchengx/'
        'contoso-data-product.git", tag = "v0.4.0" }'
    )
    moved = bump.repin(tag, "0.5.0")
    assert 'tag = "v0.5.0"' in moved

    # And a pin already current must be left alone, so the script can run on
    # every release without opening seven no-op pull requests.
    assert bump.repin(bump.repin(wheel, "0.5.0"), "0.5.0") == bump.repin(wheel, "0.5.0")


def test_update_pin_moves_either_form_and_is_idempotent(tmp_path, monkeypatch):
    """A leaf raises its own bump, so this runs in seven repositories.

    Rewriting only the form whoever wrote it had in front of them is how a leaf
    silently stops being bumped: five leaves pin a wheel URL and one pins a git
    tag.
    """
    monkeypatch.setattr(show, "latest_release", lambda timeout=10.0: "9.9.9")

    wheel = tmp_path / "wheel.toml"
    wheel.write_text(
        'contoso-data-product = { url = "https://github.com/calvinchengx/'
        'contoso-data-product/releases/download/v0.1.6/'
        'contoso_data_product-0.1.6-py3-none-any.whl" }\n',
        encoding="utf-8",
    )
    changed, message = show.update_pin(wheel)
    assert changed, message
    assert "contoso_data_product-9.9.9-py3-none-any.whl" in wheel.read_text()
    assert "0.1.6" not in wheel.read_text()

    tag = tmp_path / "tag.toml"
    tag.write_text(
        'contoso-data-product = { git = "https://github.com/calvinchengx/'
        'contoso-data-product.git", tag = "v0.4.0" }\n',
        encoding="utf-8",
    )
    changed, _ = show.update_pin(tag)
    assert changed and 'tag = "v9.9.9"' in tag.read_text()

    # A second run must do nothing, so a daily schedule does not open a PR a day.
    changed, message = show.update_pin(wheel)
    assert not changed and "already pinned" in message


def test_update_pin_reports_rather_than_writes_when_it_cannot_ask(tmp_path, monkeypatch):
    def unreachable(timeout=10.0):
        raise OSError("no route to host")

    monkeypatch.setattr(show, "latest_release", unreachable)
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("unchanged\n", encoding="utf-8")
    changed, message = show.update_pin(pyproject)
    assert not changed
    assert "could not ask" in message
    assert pyproject.read_text() == "unchanged\n", "a failed lookup rewrote the pin"
