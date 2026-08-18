# contoso-data-product

[![CI](https://github.com/calvinchengx/contoso-data-product/actions/workflows/ci.yml/badge.svg)](https://github.com/calvinchengx/contoso-data-product/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

The Contoso **data product**: bronze/silver Spark logic, gold dbt SQL and its
tests, and the ODCS contract identities those tests become.

It is a **package, not a platform.** There is no workspace here, no warehouse,
no catalog, no endpoint and no credential. A consumer binds those and calls in.

## Why this is its own repository

A data engineer writes the product once. Where it runs is somebody else's
decision, and it changes: the same bronze, silver and gold ship to Fabric and
to Databricks today.

If the transforms lived inside one platform repository, the other would copy
them, and **the copy is where the claim dies.** Two `fct_sales.sql` files agree
until the day someone fixes a bug in one of them. Keeping the product in a
package makes that failure impossible rather than discouraged: consumers depend
on it, and a change lands in both runtimes or in neither.

| consumer | runtime | switch |
|---|---|---|
| [fabric-platform-notebook-pipelines](https://github.com/calvinchengx/fabric-platform-notebook-pipelines) | Microsoft Fabric | `FABRIC_TARGET` |
| [databricks-platform-jobs](https://github.com/calvinchengx/databricks-platform-jobs) | Databricks | `DATABRICKS_TARGET` |

## What a consumer calls

```python
from contoso_product import run_bronze, run_silver, gold_dir

metrics = run_bronze(spark, landing=landing, tables=tables, day=day, ...)
metrics = run_silver(spark, tables=tables)
# dbt --project-dir $(python -c 'from contoso_product import gold_dir; print(gold_dir())')
```

`run_bronze` and `run_silver` take a **Spark session the consumer supplies** and
return the metrics they observed. They take paths, not ids. `gold_dir()` is the
absolute path to the dbt project, so a consumer points dbt at it rather than
vendoring the models.

Also exported: `MONEY` (`decimal(19,4)`), `RATE` (`decimal(19,6)`) and
`COUNTRY`, so both runtimes conform money and countries identically instead of
each picking a precision.

## The gold project

`src/contoso_product/gold/` is an ordinary dbt project, portable by
construction:

- **9 models**: 5 dimensions (`dim_country`, `dim_customer`, `dim_date`,
  `dim_party`, `dim_product`) and 4 facts (`fct_sales`, `fct_orders`,
  `fct_daily_revenue`, `fct_revenue_summary`).
- **27 tests**: 22 declared in `schema.yml`, plus 5 singular tests that assert
  things a column-level test cannot. `revenue_summary_loses_no_revenue.sql`
  checks the aggregate against its own source; `fiscal_year_is_not_the_calendar_year.sql`
  exists because that is the bug everyone writes once.
- **4 dialect macros**, in `macros/flag.sql`. T-SQL wants `cast(x as bit)` and
  `datepart(quarter, …)`; Databricks wants `boolean`, `quarter()` and `string`
  rather than `varchar(n)`. Every such leak goes through a macro, so a model is
  never forked per warehouse. `test_no_t_sql_bit_in_models` fails if one leaks
  back into a model.

The dbt tests are also the **contract**. `contracts.py` derives ODCS identities
from `schema.yml` rather than restating columns, so quality is defined once and
published to the catalog, not typed a second time for governance.

## The dual-runtime witness

Two green pipelines are not evidence that two runtimes agree. They agree when
the **numbers** agree:

```sh
uv run scripts/compare_products.py --fabric <snapshot> --databricks <snapshot>
```

It fails unless both report the same `fct_revenue_summary` aggregates and the
same contract names. A third runtime can be passed with `--snowflake`, where a
`dialect_gap` key records a **named** gap rather than letting a silent
difference pass as a match.

## Working on it

```sh
uv sync --extra compare
uv run pytest tests -q
```

No Docker, no emulator, no credentials: the tests here are about the product,
and the runtimes are exercised by the consumers. That is also why this package
has **no runtime dependencies**. It must install cleanly into a Fabric
notebook, a Databricks job cluster, or a laptop, and something it dragged in
would become something those environments have to agree about.

Apache-2.0.

## Related projects

This package is consumed by three platforms, which is the point of it being a
package rather than one: [`fabric-platform-notebook-pipelines`](https://github.com/calvinchengx/fabric-platform-notebook-pipelines),
[`databricks-platform-jobs`](https://github.com/calvinchengx/databricks-platform-jobs)
and
[`snowflake-platform-tasks`](https://github.com/calvinchengx/snowflake-platform-tasks).

Each runs on its own emulator — `fabric-emulator`, `databricks-emulator` and
`snowflake-emulator` — the first two members of the [**azure-emulators**](https://github.com/calvinchengx/azure-emulators)
family, the third a peer of it.
