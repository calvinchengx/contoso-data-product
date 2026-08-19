"""The Contoso data product — transforms and gold SQL, no platform wire.

A consumer (Fabric or Databricks) binds paths, sessions, and catalogs.
This package does not import fabric-target or databricks-target.
"""

from .bronze import run_bronze
from .bronze_contract import bronze_contract, check_bronze
from .silver import COUNTRY, MONEY, RATE, run_silver

__all__ = [
    "COUNTRY",
    "bronze_contract",
    "check_bronze",
    "MONEY",
    "RATE",
    "gold_dir",
    "run_bronze",
    "run_silver",
    "silver_dir",
]


def gold_dir():
    """Absolute path to the portable dbt gold project (models, macros, tests)."""
    from pathlib import Path

    return Path(__file__).resolve().parent / "gold"


def silver_dir():
    """Absolute path to the portable dbt silver project.

    THE CANONICAL SILVER, and the reason this function exists. Silver used to
    live in the Fabric Airflow leaf as the only dbt implementation, while this
    package carried a second one in PySpark -- two definitions of one layer,
    agreeing because they had been measured to, not because anything made them.
    A consumer points dbt at this path exactly as it points at `gold_dir()`,
    so the models cannot be vendored and cannot drift.

    `run_silver` is the OTHER runner over these same models, for cells that
    have a Spark session and no dbt (a Fabric notebook, a Databricks
    `spark_python_task`). It is a runner, not a second definition.
    """
    from pathlib import Path

    return Path(__file__).resolve().parent / "silver"
