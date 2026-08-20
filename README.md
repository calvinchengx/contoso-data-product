# contoso-data-product

[![CI](https://github.com/calvinchengx/contoso-data-product/actions/workflows/ci.yml/badge.svg)](https://github.com/calvinchengx/contoso-data-product/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

The Contoso **data product**: bronze/silver Spark logic, gold dbt SQL and its
tests, and the ODCS contract identities those tests become.

It is a **package, not a platform.** There is no workspace here, no warehouse,
no catalog, no endpoint and no credential. A consumer binds those and calls in.

It is also the **core of a family**: seven leaf products (one per platform, in
that platform's idiom) depend on it by tag, and seven platforms run them. The
layout is [`docs/00-family.md`](docs/00-family.md); the plan and every cell's
status is [`docs/01-plan.md`](docs/01-plan.md); what may live where is
[`RULES.md`](RULES.md).

|  | Fabric | Databricks | Snowflake |
|---|---|---|---|
| **Airflow 3** | ✅ | ⬜ | ⬜ |
| **engine-native** | ✅ | 🟡 | 🔴 |
| **built-in Airflow** | ⬜ | — | — |

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

## What the product contains

Generated from the package, never hand-listed. `python -m contoso_product.show`
prints it, `--into <dir>` copies the SQL somewhere you can read it, and
`--check README.md` fails when this block falls behind the package.

<!-- BEGIN product inventory: python -m contoso_product.show --markdown -->

The product is [`contoso-data-product`](https://github.com/calvinchengx/contoso-data-product/tree/v0.5.0) at **v0.5.0**, the version this repository pins. It is not vendored here: these files live there and are staged locally by `make show-product`.

**silver**: 8 models, 1 singular test

- [`silver_customers`](https://github.com/calvinchengx/contoso-data-product/blob/v0.5.0/src/contoso_product/silver/models/silver_customers.sql)
- [`silver_fx_daily`](https://github.com/calvinchengx/contoso-data-product/blob/v0.5.0/src/contoso_product/silver/models/silver_fx_daily.sql)
- [`silver_orders`](https://github.com/calvinchengx/contoso-data-product/blob/v0.5.0/src/contoso_product/silver/models/silver_orders.sql)
- [`silver_party`](https://github.com/calvinchengx/contoso-data-product/blob/v0.5.0/src/contoso_product/silver/models/silver_party.sql)
- [`silver_product_hierarchy`](https://github.com/calvinchengx/contoso-data-product/blob/v0.5.0/src/contoso_product/silver/models/silver_product_hierarchy.sql)
- [`silver_quarantine_orders`](https://github.com/calvinchengx/contoso-data-product/blob/v0.5.0/src/contoso_product/silver/models/silver_quarantine_orders.sql)
- [`silver_web_customers`](https://github.com/calvinchengx/contoso-data-product/blob/v0.5.0/src/contoso_product/silver/models/silver_web_customers.sql)
- [`silver_web_order_lines`](https://github.com/calvinchengx/contoso-data-product/blob/v0.5.0/src/contoso_product/silver/models/silver_web_order_lines.sql)

Assertions over silver, each failing the build on its own:

- [`silver_orders_never_holds_a_non_positive_quantity`](https://github.com/calvinchengx/contoso-data-product/blob/v0.5.0/src/contoso_product/silver/tests/silver_orders_never_holds_a_non_positive_quantity.sql)

**gold**: 9 models, 5 singular tests

- [`dim_country`](https://github.com/calvinchengx/contoso-data-product/blob/v0.5.0/src/contoso_product/gold/models/dim_country.sql)
- [`dim_customer`](https://github.com/calvinchengx/contoso-data-product/blob/v0.5.0/src/contoso_product/gold/models/dim_customer.sql)
- [`dim_date`](https://github.com/calvinchengx/contoso-data-product/blob/v0.5.0/src/contoso_product/gold/models/dim_date.sql)
- [`dim_party`](https://github.com/calvinchengx/contoso-data-product/blob/v0.5.0/src/contoso_product/gold/models/dim_party.sql)
- [`dim_product`](https://github.com/calvinchengx/contoso-data-product/blob/v0.5.0/src/contoso_product/gold/models/dim_product.sql)
- [`fct_daily_revenue`](https://github.com/calvinchengx/contoso-data-product/blob/v0.5.0/src/contoso_product/gold/models/fct_daily_revenue.sql)
- [`fct_orders`](https://github.com/calvinchengx/contoso-data-product/blob/v0.5.0/src/contoso_product/gold/models/fct_orders.sql)
- [`fct_revenue_summary`](https://github.com/calvinchengx/contoso-data-product/blob/v0.5.0/src/contoso_product/gold/models/fct_revenue_summary.sql)
- [`fct_sales`](https://github.com/calvinchengx/contoso-data-product/blob/v0.5.0/src/contoso_product/gold/models/fct_sales.sql)

Assertions over gold, each failing the build on its own:

- [`both_selling_systems_reach_the_pack`](https://github.com/calvinchengx/contoso-data-product/blob/v0.5.0/src/contoso_product/gold/tests/both_selling_systems_reach_the_pack.sql)
- [`every_country_resolves_to_the_dimension`](https://github.com/calvinchengx/contoso-data-product/blob/v0.5.0/src/contoso_product/gold/tests/every_country_resolves_to_the_dimension.sql)
- [`fiscal_year_is_not_the_calendar_year`](https://github.com/calvinchengx/contoso-data-product/blob/v0.5.0/src/contoso_product/gold/tests/fiscal_year_is_not_the_calendar_year.sql)
- [`money_is_never_stored_as_float`](https://github.com/calvinchengx/contoso-data-product/blob/v0.5.0/src/contoso_product/gold/tests/money_is_never_stored_as_float.sql)
- [`revenue_summary_loses_no_revenue`](https://github.com/calvinchengx/contoso-data-product/blob/v0.5.0/src/contoso_product/gold/tests/revenue_summary_loses_no_revenue.sql)

<!-- END product inventory -->

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
