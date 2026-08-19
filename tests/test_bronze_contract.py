"""Bronze is a contract. These are the teeth."""

from __future__ import annotations

import pathlib
import re

from contoso_product import bronze_contract, check_bronze

ROOT = pathlib.Path(__file__).resolve().parent.parent
SILVER = ROOT / "src" / "contoso_product" / "silver"


def test_every_bronze_source_declares_its_columns():
    """A source added without columns is a contract nobody can check.

    The prose in sources.yml has always said the shape is not negotiable. It
    said so while nothing verified it, and a platform landed its JSON feeds in
    a single `doc` column -- which silver reported four layers later as
    `Binder Error: Table "o" does not have a column named "lines"`.
    """
    declared = bronze_contract()
    names = re.findall(r"- name: \"\{\{ var\('([a-z_]+)'\) \}\}\"", (SILVER / "models" / "sources.yml").read_text(encoding="utf-8"))
    assert names, "sources.yml names no bronze tables"
    missing = [n for n in names if n not in declared]
    assert not missing, (
        f"these bronze sources declare no columns: {missing}. A source without "
        f"a column list cannot be checked, so silver finds out inside a model"
    )


def test_the_contract_names_the_same_tables_dbt_project_does():
    """The var names are the contract's keys. If the two drift, a platform
    overriding `bronze_pos_orders` would satisfy a contract nothing reads."""
    project = (SILVER / "dbt_project.yml").read_text(encoding="utf-8")
    for table in bronze_contract():
        assert re.search(rf"^\s+{re.escape(table)}:", project, re.MULTILINE), (
            f"{table} is declared in sources.yml but has no default in "
            f"dbt_project.yml, so no platform can override it by name"
        )


def test_a_missing_column_is_a_breach():
    problems = check_bronze({"bronze_web_orders": ["doc"]})
    assert any("bronze_web_orders" in p and "lines" in p for p in problems), problems


def test_a_missing_table_is_a_breach():
    problems = check_bronze({})
    assert all("not present" in p for p in problems)
    assert len(problems) == len(bronze_contract())


def test_extra_columns_are_not_a_breach():
    """Bronze may carry more than silver reads -- bronze_pos_customers has 101
    columns and silver reads six. A contract that forbade that would make every
    new vendor field a breaking change."""
    contract = bronze_contract()
    observed = {t: cols + ["a_field_the_vendor_added_later"] for t, cols in contract.items()}
    assert check_bronze(observed) == []


def test_case_does_not_decide_it():
    """Snowflake upper-cases unquoted identifiers and Spark does not. A
    contract that failed on that would be about spelling, not shape."""
    contract = bronze_contract()
    observed = {t: [c.upper() for c in cols] for t, cols in contract.items()}
    assert check_bronze(observed) == []


def test_the_contract_is_not_empty():
    contract = bronze_contract()
    assert len(contract) >= 8, contract
    assert "lines" in contract["bronze_web_orders"], (
        "the column whose absence started this must be in the contract"
    )
