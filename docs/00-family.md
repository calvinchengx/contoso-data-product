# 00 — The family

One data product. Three engines. Four kinds of orchestrator. **Same numbers in
every cell.** This document is the shape of that claim; [`01-plan.md`](01-plan.md)
is its state.

## The claim

A data product is defined by its **outputs** — the gold star, its five ODCS
contracts, `revenue_usd 129,341,157.6700 · sale_lines 474,044` — not by the
technology that computed them. The family exists to prove that one such product
runs, unchanged in what it computes, on Fabric, Databricks and Snowflake, and
under both an external Apache Airflow 3 and each engine's own scheduler.

Two green pipelines are not that proof. The proof is `compare_products.py`:
every runtime writes the same `product_snapshot.json`, and the family is green
only when the aggregates and the contract names agree — and are not two
nothings.

## The matrix

Rows are engines. Columns are orchestrators. Every cell is one **leaf product**
run by one **platform**; every leaf depends on the **core** by tag.

|  | Fabric | Databricks | Snowflake |
|---|---|---|---|
| **sources** | `contoso-sources` — the vendors, one declaration for every cell |||
| **core product** | `contoso-data-product` — transform SQL, contracts, expected numbers, once |||
| **product · Airflow 3** | `contoso-data-product-fabric-airflow3` | `contoso-data-product-databricks-airflow3` | `contoso-data-product-snowflake-airflow3` |
| **product · engine-native** | `contoso-data-product-fabric-notebook-pipelines` | `contoso-data-product-databricks-jobs` | `contoso-data-product-snowflake-tasks` |
| **product · built-in Airflow** | `contoso-data-product-fabric-airflow-builtin` | — | — |
| **platform · Airflow 3** | `fabric-platform-airflow3` | `databricks-platform-airflow3` | `snowflake-platform-airflow3` |
| **platform · engine-native** | `fabric-platform-notebook-pipelines` | `databricks-platform-jobs` | `snowflake-platform-tasks` |
| **platform · built-in Airflow** | `fabric-platform-airflow-builtin` | — | — |

Fabric has a third column because Fabric has a third orchestrator: its
`ApacheAirflowJob` item is a real Apache Airflow 2 sidecar, distinct from both
an external Airflow 3 and from Fabric's own notebooks and Data Pipelines.

Names follow one pattern. Platforms are `<engine>-platform-<orchestrator>`;
leaves are `contoso-data-product-<engine>-<orchestrator>`; a platform runs the
leaf with the matching suffix. The orchestrator token is `airflow3` for the
external Airflow and the engine's own word for its native one.

## The four tiers, and what may live in each

Everything in the family is one of four things. Which one decides where it goes.

| tier | holds | must not hold | changes when |
|---|---|---|---|
| **sources** | vendor declarations, OpenAPI specs, simulator scripts, fixture generators pinned to a release | anything about a consumer | a vendor changes |
| **core product** | ingest fetch logic, bronze, dbt silver, dbt gold, ODCS contracts, expected numbers, `compare_products.py` | a DAG, a job spec, a notebook, a runner, an endpoint, a credential | the business changes what the product *is* |
| **leaf product** | exactly what a team on that platform would write: a DAG *or* a job spec *or* notebooks *or* a task graph, plus the sink and dbt profile that platform needs | transform SQL, a contract, an expected number, a second copy of anything in core | that platform's idiom changes |
| **platform** | compose, emulator pins, vendors stood up from `contoso-sources`, provisioning, target resolver, connections | any Contoso name, any product file | the platform's infrastructure changes |

Two consequences worth stating plainly:

- **The step order is written once per leaf, on purpose.** A Jobs spec does not
  look like a DAG and should not; a leaf that generated its runner from a
  shared graph would be less readable to the team it is for. What is *not*
  written per leaf is what the steps compute.
- **A leaf is small.** Someone on Fabric opens the Fabric leaf and sees a DAG,
  a `pyproject.toml`, and a README. They do not see Snowflake.

## What is singular, and how that is enforced

| written once, in | enforced by |
|---|---|
| transform SQL (silver, gold models) | core `RULES.md` §1; every leaf's `test_the_product_is_imported_not_restated` |
| the five contracts | same |
| the expected numbers | `compare_products.py` — a leaf that disagrees fails the family, it does not get its own numbers |
| the vendors and their bytes | every platform generates its vendor stack from `contoso-sources/sources.yaml`; none carries a vendor of its own |
| the emulator-or-real switch | each engine's published `*-target` package; a platform adds policy, never restates the contract |

Where the same thing genuinely exists twice, it is a **runner over the same
definition, tested equal** — never a second definition. Core holds dbt silver
as canonical and a PySpark bronze/silver for the notebook-native cells; the
PySpark path executes the same SQL and a test asserts the same silver metrics.
That is the one place two implementations are allowed, and the test is what
allows it.

## Extending the matrix

The grid is open on both axes, and the cost of adding to either is bounded on
purpose: **core does not change.** If adding a row or a column ever requires
touching `contoso-data-product`, the design has failed and `RULES.md` should
have caught it.

**Adding an engine (a row)** needs:

1. an `<engine>-target` package — the emulator-or-real switch, if an emulator
   exists; otherwise just "real";
2. a **dbt adapter** — the hard requirement, because silver and gold are dbt;
3. a bronze path — Spark if the engine speaks Spark, else SQL
   (`COPY INTO`, `read_files`);
4. a `Sink` for ingest — about thirty lines;
5. then one leaf and one platform per orchestrator it is to run under.

**Adding an orchestrator (a column)** needs one leaf per engine, written in
that orchestrator's idiom, and one platform per engine that stands it up.
Nothing else.

**Not every cell gets built.** The grid grows multiplicatively — three engines
by four orchestrator kinds is already seven cells; add one engine and one
orchestrator and it is thirteen. So a cell earns a repository only when it
**proves something no existing cell proves.** DuckDB under Airflow 3 proves the
product needs no cloud; DuckDB under Dagster proves assets-native
orchestration; DuckDB under Prefect proves nothing the other two did not, and
stays reserved or is never added. Reserved-empty repos are cheap; witnessed
cells are the expensive thing, and [`01-plan.md`](01-plan.md) says which cells
are load-bearing.

Candidates that fit well, for the record: **DuckDB / MotherDuck** (`dbt-duckdb`,
bronze native, local DuckDB is the emulator tier); **Postgres** (`dbt-postgres`,
the no-cloud baseline); **BigQuery** (`dbt-bigquery`, and a real emulator
exists); **Dagster** (`dagster-dbt` makes every model a software-defined asset —
the strongest second orchestrator column); **Prefect 3** (`prefect-dbt`, plain
Python flows). **LakeSail** is already the Spark engine under two emulators, so
bronze and silver are proven; gold is the open question, because no dbt adapter
speaks Spark Connect to it — a spike, not a row, until that is answered.
**SQLMesh** is not a row or a column but a peer of dbt, and adding it would
mean a second canonical silver, which `RULES.md` §1 forbids unless tested
equal.

Two tools worth adding independent of any cell: **sqlglot** in core CI, to
transpile every model to every target dialect at test time and catch "this
only parses on Fabric" without standing up an engine; and **OpenLineage with
Marquez** as a platform sidecar, so cross-cell lineage can be compared the way
`compare_products.py` compares cross-cell numbers.

## How to read a cell's status

| mark | meaning |
|---|---|
| ✅ | green, and its snapshot matches the family's numbers |
| 🟡 | matches the numbers, but not yet in the shape its name claims |
| 🔴 | not producing the numbers; a named gap |
| ⬜ | reserved — LICENSE and README, nothing else |

Status lives in [`01-plan.md`](01-plan.md), not here.
