# 01 — The plan

The state of the matrix in [`00-family.md`](00-family.md), and the order the
empty cells get filled. **This file changes; that one should not.** When a
cell turns green, the PR that did it updates the row here and points at the
snapshot.

_Last updated: 2026-08-18._

## Where every cell stands

| cell | product | platform | status | evidence / gap |
|---|---|---|---|---|
| Fabric · Airflow 3 | `contoso-data-product-fabric-airflow3` (today: `contoso-airflow-data-product`) | `fabric-platform-airflow3` | ✅ | 36/36 tasks; `129,341,157.6700 / 2,800,504.4000 / 474,044`; 18 self-declared assets |
| Fabric · notebooks + pipelines | `contoso-data-product-fabric-notebook-pipelines` (today: inside the platform) | `fabric-platform-notebook-pipelines` | ✅ | same numbers, all 116 repo tests; product still lives inside the platform repo |
| Fabric · built-in Airflow | `contoso-data-product-fabric-airflow-builtin` | `fabric-platform-airflow-builtin` | ⬜ | needs the Airflow-2 shape of the DAG |
| Databricks · Airflow 3 | `contoso-data-product-databricks-airflow3` | `databricks-platform-airflow3` | ⬜ | mostly reuses the Fabric Airflow 3 leaf |
| Databricks · Jobs | `contoso-data-product-databricks-jobs` (today: inside the platform) | `databricks-platform-jobs` | 🟡 | numbers match exactly; runs as host scripts, not Jobs; product still inside the platform |
| Snowflake · Airflow 3 | `contoso-data-product-snowflake-airflow3` | `snowflake-platform-airflow3` | ⬜ | Snowflake has no bronze or silver yet |
| Snowflake · Tasks | `contoso-data-product-snowflake-tasks` | `snowflake-platform-tasks` | 🔴 | gold-only over an empty seeded silver; emulator has no Tasks |

`contoso-sources` has **no remote**. Five READMEs point at it.

## The gaps, and who owns each

Every empty or amber cell is blocked on one or more of these. A gap is named
here so that it is a line item, not a surprise.

| # | gap | blocks | owner | shape of the fix |
|---|---|---|---|---|
| G1 | **Two silvers.** PySpark `run_silver` in core; dbt-fabricspark models in the Airflow leaf. They agree today by measurement, not by structure. | everything | core | dbt silver moves into core as canonical; PySpark runs the same SQL; a test asserts equal silver metrics |
| G2 | **Two repos contain their product.** `fabric-platform-notebook-pipelines` and `databricks-platform-jobs` hold ingest, notebooks, bronze/silver/gold runners. | those two cells being honest | platform + leaf | split: platform keeps compose/provision/vendors/target; the rest becomes the leaf |
| G3 | **Airflow 2.10.5 ≠ Airflow 3.3.1.** Task SDK vs `airflow.decorators`; `Asset` vs `Dataset`; api-server execution vs direct import; DAG bundle vs OneLake sync. | Fabric · built-in Airflow | leaf | a second DAG in the 2.x idiom, in its own leaf; cosmos pinned to a 2.10-compatible release |
| G4 | **`dbt_task` not implemented**, and the statement agent is not a shell. Gold runs from the host today. | Databricks · Jobs | **databricks-emulator** | implement `dbt_task` (agent image carries `dbt-databricks`, runs against the warehouse endpoint) — real Databricks has it natively |
| G5 | **Snowflake has no bronze or silver.** The platform seeds empty tables and gold reports a `dialect_gap`. | both Snowflake cells | core + leaf | SQL bronze (`COPY INTO` from a stage) and dbt-snowflake silver; a build, not a port |
| G6 | **Snowflake Tasks not implemented** in the emulator (`parity.md`: 🔴). | Snowflake · Tasks | **snowflake-emulator** | `CREATE TASK … AFTER … AS …` and task graphs |
| G7 | **`money_is_never_stored_as_float` read SQL Server's `INFORMATION_SCHEMA`.** Empty in Unity Catalog, so it passed vacuously on Databricks — while that engine's aggregate money columns were `double`. **Fix written**: `macros/reflect.sql` (`INFORMATION_SCHEMA` on Fabric, `DESCRIBE TABLE` on Spark engines) and the contract rewritten over it, unit-tested. **Not yet witnessed** on any target; expected to *fail* on Databricks until G8 is resolved or the star casts its aggregates. | contract honesty | core | witness on Fabric, Databricks (expect red — that is the point), Snowflake once G5 lands |
| G8 | **Sail demotes `sum(decimal(19,4))` to `double`.** Measured: `typeof(sum(amount_usd))` → `double`. Real Spark widens to `decimal(29,4)`. | Databricks money columns | **fabric-emulator-sail** | upstream report; the databricks snapshot casts back to `DECIMAL(19,4)` in the engine meanwhile |
| G9 | **Stale Spark Connect session never re-established** by the shared agent (`session … is not running`). Restarting the agent clears it. | any Sail-backed cell, intermittently | **fabric-emulator spark-agent** | reconnect on session-not-found |
| G10 | **`contoso-sources` unpublished.** | anyone cloning a platform | — | `gh repo create` |

## Order of work

Each step is one PR (or one PR per repo it touches), and each names the cell it
turns green and the gap it closes.

| # | step | closes | turns green |
|---|---|---|---|
| 0 | Commit the verified databricks sources work; publish `contoso-sources`; write this plan | G10 | — |
| 1 | **Rename and reserve.** `contoso-airflow-data-product` → `contoso-data-product-fabric-airflow3`; create the six other leaves empty | — | — (shape) |
| 2 | **Unify core.** dbt silver models move down from the Airflow leaf; PySpark path executes the same SQL; silver-metrics equality test; `RULES.md` in core | G1 | — (foundation) |
| 3 | **Split the two platforms that contain their product.** Notebook-pipelines and databricks-jobs each become platform + leaf; both leaves pin core by tag | G2 | Fabric · notebooks ✅ honest; Databricks · Jobs stays 🟡 |
| 4 | **Databricks · Airflow 3.** New leaf from the Fabric Airflow 3 leaf: volume sink, Databricks profile; new platform | — | Databricks · Airflow 3 ✅ |
| 5 | **Snowflake · Airflow 3.** SQL bronze, dbt-snowflake silver in core; stage sink; new leaf and platform | G5 | Snowflake · Airflow 3 ✅; Snowflake · Tasks moves 🔴 → 🟡 |
| 6 | **`dbt_task` in databricks-emulator**, then the Jobs leaf becomes a real Jobs spec | G4 | Databricks · Jobs 🟡 → ✅ |
| 7 | **Airflow-2 leaf** on fabric-emulator's `ApacheAirflowJob`; new platform | G3 | Fabric · built-in Airflow ✅ |
| 8 | **Tasks in snowflake-emulator**, then the Tasks leaf | G6 | Snowflake · Tasks ✅ |
| — | G7 (dialect macro for the money contract) and G8/G9 (upstream) run alongside, not in sequence | G7 G8 G9 | contract honesty in every cell |

Steps 2 and 3 are the ones that make the rest cheap: after them, adding a cell
is a small leaf plus a small platform, and nothing in core moves.

## Definition of done, per cell

A cell is ✅ only when all of these hold. Anything less is 🟡 and says why.

1. The platform clones and runs alone: published wheels, no sibling path, no
   Contoso name.
2. The leaf contains only what its platform's team would write, and depends on
   core by **tag**.
3. `make verify` (or the platform's equivalent) is green **through the
   orchestrator the cell is named for** — not from a host script standing in
   for it.
4. Its `product_snapshot.json` passes `compare_products.py` against the
   family's numbers, and the five contract names match.
5. Every gap it still carries is a row in the table above, not a comment in a
   log.
