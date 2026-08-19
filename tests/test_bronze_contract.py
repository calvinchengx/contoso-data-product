"""Bronze is a contract. These are the teeth."""

from __future__ import annotations

import pathlib
import re

from contoso_product import bronze_contract, check_bronze

ROOT = pathlib.Path(__file__).resolve().parent.parent
SILVER = ROOT / "src" / "contoso_product" / "silver"


def sources_models_actually_read() -> set[str]:
    """The bronze sources a silver model references, read from the models."""
    out = set()
    for model in (SILVER / "models").glob("*.sql"):
        out |= set(re.findall(r"source\('bronze', var\('([a-z_]+)'\)\)", model.read_text(encoding="utf-8")))
    return out


def test_the_contract_covers_exactly_what_silver_reads():
    """Every source a model reads declares its columns, and no source that
    nothing reads carries a contract.

    Both halves were learned the hard way. The first is the point of the
    contract at all. The second is a correction: this file's first version
    declared columns for `bronze_web_products` and `bronze_erp_customer_changes`,
    which NO model reads -- seven column names invented for one of them, and
    four for the other that happened to match by luck. The invented list failed
    against a real bronze and accused the platform of a breach that was the
    contract's own.

    A contract for a table nobody reads cannot be verified against anything,
    so it is a claim with no way of being wrong.
    """
    declared = set(bronze_contract())
    read = sources_models_actually_read()
    assert read, "no model references a bronze source; the parser is wrong"
    assert declared == read, (
        f"the contract and the models disagree.\n"
        f"  declared but unread: {sorted(declared - read)}\n"
        f"  read but undeclared: {sorted(read - declared)}"
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
    assert len(contract) == 6, (
        f"six bronze sources are read by a silver model; the contract has "
        f"{len(contract)}: {sorted(contract)}"
    )
    assert "lines" in contract["bronze_web_orders"], (
        "the column whose absence started this must be in the contract"
    )
