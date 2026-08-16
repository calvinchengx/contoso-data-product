# contoso-data-product

The portable Contoso **data product**: bronze/silver Spark logic, gold dbt
SQL and tests, and the ODCS contract identities those tests become.

Consumers wrap this package. They do not copy it.

- [contoso-fabric-platform](https://github.com/calvinchengx/contoso-fabric-platform) — Fabric (`FABRIC_TARGET`)
- [contoso-databricks-platform](https://github.com/calvinchengx/contoso-databricks-platform) — Databricks (`DATABRICKS_TARGET`)

```python
from contoso_product import run_bronze, run_silver, gold_dir

metrics = run_bronze(spark, landing=landing, tables=tables, day=day, ...)
metrics = run_silver(spark, tables=tables)
# dbt --project-dir $(python -c 'from contoso_product import gold_dir; print(gold_dir())')
```

Workspace ids, warehouse HTTP paths, and secret *values* do not appear here.
The consumer's target resolver turns **names** into the ids that target uses.

`scripts/compare_products.py` is the dual-runtime witness: same
`fct_revenue_summary` aggregates, same contract names.

Apache-2.0.
