"""The Contoso data product — transforms and gold SQL, no platform wire.

A consumer (Fabric or Databricks) binds paths, sessions, and catalogs.
This package does not import fabric-target or databricks-target.
"""

from .bronze import run_bronze
from .silver import COUNTRY, MONEY, RATE, run_silver

__all__ = ["COUNTRY", "MONEY", "RATE", "gold_dir", "run_bronze", "run_silver"]


def gold_dir():
    """Absolute path to the portable dbt gold project (models, macros, tests)."""
    from pathlib import Path

    return Path(__file__).resolve().parent / "gold"
