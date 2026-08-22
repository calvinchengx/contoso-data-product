# Rules for this codebase

This repository is the **core** of the Contoso family: the one place the
product is written. Everything else — seven leaf products, seven platforms —
depends on it and must not restate it. Every rule below exists to keep "one
product" a fact rather than a slogan, because the failure mode is silent: two
copies agree until the day someone fixes a bug in one of them.

Each rule names the test that enforces it. **A rule with no test is a rule we
will break** — the "enforced by" column is the honest part of this document,
and `judgement` means exactly that.

The family layout is in [`docs/00-family.md`](docs/00-family.md); the plan in
[`docs/01-plan.md`](docs/01-plan.md).

---

## 1. Written once, here

| | |
|---|---|
| **Rule** | Transform SQL (silver and gold models), the ODCS contracts, and the expected numbers exist **only in this repository**. A leaf or platform consumes them from a release; none carries a copy. |
| **Why** | `fabric-platform-notebook-pipelines` once carried its own 18-file copy of gold and a 400-line copy of silver, and the copies had diverged — the product gained a portability fix the fork never got. Nothing failed, because nothing compared them. A copy is not a risk of divergence; it is divergence with a delay. |
| **Enforced by** | every leaf's `test_the_product_is_imported_not_restated`; here, `test_gold_project_is_complete` |

| | |
|---|---|
| **Rule** | Where an implementation genuinely exists twice, it is a **runner over the same definition, tested equal** — never a second definition. dbt silver is canonical; the PySpark path executes the same SQL for notebook-native cells. |
| **Why** | The notebook cells need Spark and cannot idiomatically run dbt; that is a real constraint and the honest answer to it is a second runner. But two silvers that merely *agree by measurement* is the exact defect rule 1 exists to prevent, one layer down. |
| **Enforced by** | `test_pyspark_silver_matches_dbt_silver` *(planned — G1 in the plan)*; today: `judgement`, and `compare_products.py` at gold |

| | |
|---|---|
| **Rule** | This package has **no runtime dependencies** and names no engine. `run_bronze`/`run_silver` take a Spark session the caller supplies; `gold_dir()` is a path; nothing here opens a connection. |
| **Why** | It must install cleanly into a Fabric notebook, a Databricks job cluster, a Snowflake procedure and a laptop. Anything it dragged in becomes something all of those have to agree about, and an endpoint anywhere here is a leaf's decision leaking upward. |
| **Enforced by** | `test_no_runtime_dependencies`, `test_no_engine_named_in_core` |

## 2. What may not be here

| | |
|---|---|
| **Rule** | No DAG, no job spec, no notebook, no `CREATE TASK`, no runner of any kind. Those are **leaf** products, one per platform, in the idiom of that platform. |
| **Why** | A team on Databricks Jobs wants to open a repo and see a Databricks data product — not an Airflow-2 shim and a Snowflake task graph beside it. Readability of the leaf *is* the deliverable; the core stays small so the leaves can. |
| **Enforced by** | `test_no_orchestrator_in_core` |

| | |
|---|---|
| **Rule** | No expected number is written in a leaf or a platform. The family's numbers live in the snapshots this repository compares, and a runtime that disagrees **fails** — it does not get its own. |
| **Why** | The databricks platform once wrote a two-row fixture and published `revenue_usd 37`. It was green. It compared to nothing. Numbers that a cell can define for itself are numbers that mean nothing across cells. |
| **Enforced by** | `expected.py` states them and `assert_snapshot.py` holds one cell to them in its own CI; `compare_products.py` holds the cells to each other — `empty()` refuses a snapshot with no evidence, and any disagreement exits 1 |

## 3. Dialect

| | |
|---|---|
| **Rule** | Every engine-specific construct in a model goes through a macro in `macros/`. A model is never forked per warehouse. |
| **Why** | T-SQL wants `cast(x as bit)` and `datepart(quarter, …)`; Spark wants `boolean` and `quarter()`; Snowflake wants its own. One `fct_sales.sql` with four macros is one product; four `fct_sales.sql` files is four. |
| **Enforced by** | `test_no_t_sql_bit_in_models` |

| | |
|---|---|
| **Rule** | A contract that reads catalog metadata does so through a **dialect macro**, and a contract that would pass on an empty result must first prove the result is not empty. |
| **Why** | `money_is_never_stored_as_float` reads SQL Server's `INFORMATION_SCHEMA.COLUMNS`. Unity Catalog returns nothing there, so it passes on Databricks — including *now*, while that engine's aggregate money columns are `double`. A contract that cannot see the thing it guards is not a contract. |
| **Enforced by** | `test_the_float_contract_reflects_on_every_target`, `test_reflection_is_written_once_and_covers_both_dialect_families` — the `reflected_columns` macro in `macros/reflect.sql`; still to be *witnessed* on Databricks and Snowflake (G7) |

## 4. Consumption

| | |
|---|---|
| **Rule** | Leaves and platforms depend on this package **by git tag or published wheel**, never by sibling path. |
| **Why** | A path dependency resolves only on a machine that happens to have both checkouts side by side. Every consumer must clone and build alone, or it proves nothing about what anyone else can do with a release. |
| **Enforced by** | each consumer's `test_no_dependency_comes_from_a_sibling_checkout` |

| | |
|---|---|
| **Rule** | A release of this package is the unit of change. A leaf moves its tag deliberately; nothing tracks `main`. |
| **Why** | Seven leaves pinning `main` is seven ways for a core change to break a cell nobody was looking at. A tag bump is a PR in the leaf, reviewed as such. |
| **Enforced by** | `judgement` |
