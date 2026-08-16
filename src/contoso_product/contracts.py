"""ODCS contract identities published to OpenMetadata.

Derived from gold/models/schema.yml tests — one definition of quality.
Consumers publish these; they do not retype columns.
"""

from __future__ import annotations

from pathlib import Path

PRODUCT_NAME = "contoso-analytics"
DOMAIN = "contoso-commerce"
METRICS = (
    "revenue_usd",
    "cancelled_revenue_usd",
    "fiscal_year",
    "product_segment",
    "customer_segment",
    "channel_system",
)


def schema_yml() -> Path:
    return Path(__file__).resolve().parent / "gold" / "models" / "schema.yml"


def contract_id(table: str) -> str:
    return f"{PRODUCT_NAME}.{table}"
