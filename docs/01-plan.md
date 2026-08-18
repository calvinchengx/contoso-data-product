# 01 — The plan

The state of the matrix in [`00-family.md`](00-family.md), and the order the
empty cells get filled. **This file changes; that one should not.** When a
cell turns green, the PR that did it updates the row here and points at the
snapshot.

_Last updated: 2026-08-18._

## Where every cell stands

| cell | product | platform | status | evidence / gap |
|---|---|---|---|---|
| Fabric · Airflow 3 | `contoso-data-product-fabric-airflow3` | `fabric-platform-airflow3` | ✅ | 36/36 tasks; `129,341,157.6700 / 2,800,504.4000 / 474,044`; 18 self-declared assets |
| Fabric · notebooks + pipelines | `contoso-data-product-fabric-notebook-pipelines` (today: inside the platform) | `fabric-platform-notebook-pipelines` | ✅ | same numbers, all 116 repo tests; product still lives inside the platform repo |
| Fabric · built-in Airflow | `contoso-data-product-fabric-airflow-builtin` | `fabric-platform-airflow-builtin` | ⬜ | needs the Airflow-2 shape of the DAG |
| Databricks · Airflow 3 | `contoso-data-product-databricks-airflow3` | `databricks-platform-airflow3` | ⬜ | mostly reuses the Fabric Airflow 3 leaf |
| Databricks · Jobs | `contoso-data-product-databricks-jobs` (today: inside the platform) | `databricks-platform-jobs` | 🟡 | pulls the real vendors; bronze **and** silver match Fabric to the row (102,000 POS customers, 93,571 CDC events, 226,544 web lines, 118,000 parties) and gold agrees exactly. 🟡 is now **purely shape**: host scripts, not Jobs; product still inside the platform |
| Snowflake · Airflow 3 | `contoso-data-product-snowflake-airflow3` | `snowflake-platform-airflow3` | ⬜ | Snowflake has no bronze or silver yet |
| Snowflake · Tasks | `contoso-data-product-snowflake-tasks` | `snowflake-platform-tasks` | 🔴 | gold-only over an empty seeded silver; emulator has no Tasks |

`contoso-sources` is **published**: <https://github.com/calvinchengx/contoso-sources> (Apache 2.0, `_data/` materialised not committed). G10 closed.

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
| G7 | **`money_is_never_stored_as_float` read SQL Server's `INFORMATION_SCHEMA`.** Empty in Unity Catalog, so it passed vacuously on Databricks — while that engine's money columns read as `double`. **Fixed and released** in core **v0.1.1**: `macros/reflect.sql` (`INFORMATION_SCHEMA` on Fabric, `DESCRIBE TABLE` on Spark engines) and the contract rewritten over it. **Witnessed on Databricks**: `PASS=50 ERROR=2`, and it caught **12** genuinely-float money columns across all five gold models — the red predicted here, for the reason predicted. | contract honesty | core | witness on Fabric; Snowflake once G5 lands. Stays red on Databricks until G8 is fixed upstream. |
| G8 | **Decimal columns register in UC as `DOUBLE`, so they are read as float.** `databricks-emulator` `internal/sqlshim/shim.go` (`sparkToUC`) deliberately maps `decimal(p,s)` to `type_name: DOUBLE`; the Delta log, the Parquet physical type and `DESCRIBE` all still say `decimal(19,4)`, but the planner trusts UC. **Not** a `sum()` defect — that was this plan's earlier reading and it is wrong: a fresh `CREATE TABLE t AS SELECT CAST(1.5 AS DECIMAL(19,4)) AS m` answers `typeof(sum(m))` with `decimal(29,4)`, correctly. | Databricks money columns; G7 staying red | **databricks-emulator** ([#46](https://github.com/calvinchengx/databricks-emulator/issues/46)) | the emulator maps it that way because Sail's unity provider rejects `decimal(p,s)` (`Unsupported complex type`), so the real fix is likely upstream in Sail. The databricks snapshot casts back to `DECIMAL(19,4)` in the engine meanwhile. |
| G9 | **Stale Spark Connect session never re-established** by the shared agent (`session … is not running`). Restarting the agent clears it. | any Sail-backed cell, intermittently | **fabric-emulator spark-agent** | reconnect on session-not-found |
| ~~G10~~ | ~~**`contoso-sources` unpublished.**~~ **Closed** — published Apache 2.0, `_data/` still materialised rather than committed. | — | — | — |
| G11 | **Core is consumed by tag, so nothing in it reaches a cell without a release.** v0.1.1 shipped G7's fix; the plan had no step that says so, and a core commit that is never released is invisible to every consumer. | every cell, silently | core | tag `v*` → the release workflow builds and attaches the wheel; then bump each consumer's pin and relock. Four consumers today: two by wheel URL, one by git tag, and `snowflake-platform-tasks` by **sibling path** — which is the one that cannot be cloned alone |

## Order of work

Each step is one PR (or one PR per repo it touches), and each names the cell it
turns green and the gap it closes.

| # | step | closes | turns green |
|---|---|---|---|
| ~~0~~ | ~~Commit the verified databricks sources work; publish `contoso-sources`; write this plan~~ **Done.** Vendor-ingest committed (`databricks-platform-jobs` `9355579`); `contoso-sources` published; core **v0.1.1** cut and three consumers pinned | G10 G11 | — |
| ~~1~~ | ~~**Rename and reserve.**~~ **Done.** `contoso-airflow-data-product` → `contoso-data-product-fabric-airflow3` (repo, package name, lockfile, and every reference); the six other leaves created public with LICENSE + README. All 7 leaves and 7 platforms now exist | — | — (shape) |
| 2 | **Unify core.** dbt silver models move down from the Airflow leaf; PySpark path executes the same SQL; silver-metrics equality test; `RULES.md` in core | G1 | — (foundation) |
| 3 | **Split the two platforms that contain their product.** Notebook-pipelines and databricks-jobs each become platform + leaf; both leaves pin core by tag | G2 | Fabric · notebooks ✅ honest; Databricks · Jobs stays 🟡 |
| 4 | **Databricks · Airflow 3.** New leaf from the Fabric Airflow 3 leaf: volume sink, Databricks profile; new platform | — | Databricks · Airflow 3 ✅ |
| 5 | **Snowflake · Airflow 3.** SQL bronze, dbt-snowflake silver in core; stage sink; new leaf and platform | G5 | Snowflake · Airflow 3 ✅; Snowflake · Tasks moves 🔴 → 🟡 |
| 6 | **`dbt_task` in databricks-emulator**, then the Jobs leaf becomes a real Jobs spec | G4 | Databricks · Jobs 🟡 → ✅ |
| 7 | **Airflow-2 leaf** on fabric-emulator's `ApacheAirflowJob`; new platform | G3 | Fabric · built-in Airflow ✅ |
| 8 | **Tasks in snowflake-emulator**, then the Tasks leaf | G6 | Snowflake · Tasks ✅ |
| — | G7 (done, witnessed) and G8/G9 (upstream) run alongside, not in sequence | G7 G8 G9 | contract honesty in every cell |
| — | **Release and pin** whenever core changes — not a step but a rule; see G11 | G11 | — |

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
