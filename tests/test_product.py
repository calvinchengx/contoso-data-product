"""The product package is importable and gold SQL has no dialect leaks."""

from __future__ import annotations

from pathlib import Path

from contoso_product import COUNTRY, MONEY, RATE, gold_dir
from contoso_product.contracts import METRICS, PRODUCT_NAME, schema_yml


def test_constants():
    assert MONEY == "decimal(19,4)"
    assert RATE == "decimal(19,6)"
    assert COUNTRY["USA"] == "US"
    assert PRODUCT_NAME == "contoso-analytics"
    assert "revenue_usd" in METRICS


def test_gold_layout():
    g = gold_dir()
    assert (g / "models" / "fct_revenue_summary.sql").is_file()
    assert (g / "models" / "fct_sales.sql").is_file()
    assert (g / "macros" / "flag.sql").is_file()
    assert schema_yml().is_file()


def test_no_t_sql_bit_in_models():
    models = Path(gold_dir() / "models")
    leaked = []
    for p in models.glob("*.sql"):
        text = p.read_text(encoding="utf-8")
        if "as bit" in text.lower():
            leaked.append(p.name)
    assert leaked == [], f"T-SQL BIT leaked into portable models: {leaked}"
