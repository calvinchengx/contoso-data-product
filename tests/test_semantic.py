"""The semantic model is derived, bounded, and holds no deployment facts.

Each test here is named by a claim in semantic.py's docstring or RULES.md;
a test that guards nothing stated somewhere is decoration.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest

from contoso_product import semantic
from contoso_product.contracts import schema_yml

_CORE = Path(__file__).resolve().parents[1]


def _declared_summary_columns() -> list[str]:
    """The column names schema.yml declares for TABLE, by strict text scan.

    Not yaml.safe_load: core ships without a yaml parser on purpose, and the
    test env inheriting one from dbt is a coincidence this test refuses to
    depend on. The scan asserts it found the block, so a reformatted yml
    fails loudly instead of returning [] and passing everything vacuously.
    """
    text = schema_yml().read_text(encoding="utf-8")
    m = re.search(
        rf"^  - name: {semantic.TABLE}\n(.*?)(?=^  - name: |\Z)",
        text, re.MULTILINE | re.DOTALL)
    assert m, f"{semantic.TABLE} block not found in schema.yml -- the scan proved nothing"
    cols = re.findall(r"^      - name: (\w+)$", m.group(1), re.MULTILINE)
    assert cols, "no columns parsed from the block -- the scan proved nothing"
    return cols


def test_semantic_columns_come_from_the_gold_schema():
    # One definition of quality: the model may not carry a column the schema
    # does not declare, nor drop one it does. Either direction is drift.
    declared = set(_declared_summary_columns())
    modelled = {n for n, _ in semantic.COLUMNS}
    assert modelled == declared, (
        f"model columns and schema.yml disagree: "
        f"only in model {sorted(modelled - declared)}, "
        f"only in schema {sorted(declared - modelled)}")


def test_every_measure_references_the_table_and_a_declared_column():
    cols = {n for n, _ in semantic.COLUMNS}
    for name, dax in semantic.MEASURES.items():
        refs = re.findall(r"(\w+)\[(\w+)\]", dax)
        assert refs, f"{name!r} references no column: {dax}"
        for table, col in refs:
            assert table == semantic.TABLE, f"{name!r} reaches outside the model: {dax}"
            assert col in cols, f"{name!r} uses undeclared column {col!r}"


def test_measures_stay_inside_the_declared_dax():
    # Growing this set is a reviewed decision: every function must be one a
    # bounded evaluator answers exactly or refuses. No APPROX*, no
    # time-intelligence, nothing sampling-based.
    allowed = {"SUM"}
    for name, dax in semantic.MEASURES.items():
        used = set(re.findall(r"\b([A-Z][A-Z0-9]+)\s*\(", dax))
        assert used <= allowed, (
            f"{name!r} uses {sorted(used - allowed)}, outside the allowlist "
            f"{sorted(allowed)}: widen it deliberately or stay inside")


def test_every_family_number_has_a_measure():
    # The three numbers compare_products holds every cell to must each be
    # answerable through the model, or the semantic layer asserts less than
    # the family does.
    from importlib import util

    spec = util.spec_from_file_location(
        "compare_products", _CORE / "scripts" / "compare_products.py")
    # Asserted, not cast: both are Optional, and a script that moved should
    # fail this test by name rather than as an AttributeError three frames
    # down.
    assert spec and spec.loader, "compare_products.py not importable from scripts/"
    cp = util.module_from_spec(spec)
    spec.loader.exec_module(cp)
    numeric = [k for k in cp.KEYS if k != "contracts"]
    covered = set(semantic._MEASURE_SNAPSHOT_KEYS.values())
    assert set(numeric) <= covered, (
        f"family numbers with no measure: {sorted(set(numeric) - covered)}")


def test_expected_measures_reads_the_snapshot_and_refuses_a_subset():
    snap = {"revenue_usd": "129341157.6700",
            "cancelled_revenue_usd": "2800504.4000",
            "sale_lines": "474044"}
    got = semantic.expected_measures(snap)
    assert got["Revenue USD"] == Decimal("129341157.6700")
    assert got["Sale Lines"] == Decimal("474044")
    assert set(got) == set(semantic.MEASURES)
    with pytest.raises(KeyError, match="refusing to assert a subset"):
        semantic.expected_measures({"revenue_usd": "1"})


def test_model_bim_carries_the_callers_binding_and_no_endpoint_of_its_own():
    bim = semantic.model_bim("let Source = CALLER_SUPPLIED in Source", "dbo")
    assert bim["compatibilityLevel"] == 1604
    (table,) = bim["model"]["tables"]
    (part,) = table["partitions"]
    assert part["mode"] == "directLake"
    assert part["source"]["entityName"] == semantic.TABLE
    assert part["source"]["schemaName"] == "dbo"
    (expr,) = bim["model"]["expressions"]
    assert expr["expression"] == "let Source = CALLER_SUPPLIED in Source"
    assert part["source"]["expressionSource"] == expr["name"]
    # Nothing in the definition beyond the caller's own string may address an
    # engine -- the same ban test_no_engine_named_in_core places on the code.
    import json
    rest = json.dumps(bim).replace("CALLER_SUPPLIED", "")
    for banned in ("https://", "fabric.microsoft.com", "onelake.dfs"):
        assert banned not in rest


def test_model_bim_refuses_to_guess_the_binding():
    with pytest.raises(ValueError, match="will not invent an endpoint"):
        semantic.model_bim("", "dbo")
    with pytest.raises(ValueError, match="refusing to guess"):
        semantic.model_bim("let Source = x in Source", "  ")
