# 01 — The plan

The state of the matrix in [`00-family.md`](00-family.md), and the order the
empty cells get filled. **This file changes; that one should not.** When a
cell turns green, the PR that did it updates the row here and points at the
snapshot.

_Last updated: 2026-08-18._

## Where every cell stands

| cell | product | platform | status | evidence / gap |
|---|---|---|---|---|
| Fabric · Airflow 3 | `contoso-data-product-fabric-airflow3` | `fabric-platform-airflow3` | ✅ | **Re-witnessed on core v0.2.0** from empty volumes: 36/36 tasks, `129,341,157.6700 / 2,800,504.4000 / 474,044`, gold rows unchanged (dim_party 118,000, fct_sales 474,044, fct_revenue_summary 119). Moving silver into core changed where the models live and nothing about what they compute, which was the claim. Snapshot at `9379012` |
| Fabric · notebooks + pipelines | `contoso-data-product-fabric-notebook-pipelines` (today: inside the platform) | `fabric-platform-notebook-pipelines` | ✅ | same numbers, all 116 repo tests; product still lives inside the platform repo |
| Fabric · built-in Airflow | `contoso-data-product-fabric-airflow-builtin` | `fabric-platform-airflow-builtin` | ⬜ | needs the Airflow-2 shape of the DAG. **The emulator side is further along than this row implied**: `ApacheAirflowJob` items, a real `apache/airflow:2.10.5-python3.12` sidecar and an e2e that creates the item, uploads `dags/`, POSTs `jobs/instances?jobType=Run` and polls to `Completed` all exist and pass — so the API shape a platform needs is proven, not guessed. What is left is mostly the leaf's Airflow 2 DAG (G3), plus **G17**: the sidecar runs `SequentialExecutor` where Fabric runs `CeleryExecutor` |
| Databricks · Airflow 3 | `contoso-data-product-databricks-airflow3` | `databricks-platform-airflow3` | ⬜ | mostly reuses the Fabric Airflow 3 leaf |
| Databricks · Jobs | `contoso-data-product-databricks-jobs` (today: inside the platform) | `databricks-platform-jobs` | 🟡 | Pulls the real vendors; bronze, silver and gold all match Fabric. **The unreleased-image caveat is CLOSED.** G8 is fixed, released as `databricks-emulator` **v0.2.5**, the pin moved, and `make verify` has been re-run on a clean stack against the **published** image — pulled, not built here — reporting `PASS=52 WARN=0 ERROR=0`, govern clean, exit 0, `contract_failures` absent, and `129341157.6700 / 2800504.4000 / 474044`. `compare_products` exits 0 three ways against that image, so the agreement is now reproducible by anyone. Preconditions were checked rather than assumed: image digest, one ERP replay (watermark 93,571), snapshot deleted first. **What keeps it 🟡 is now ONE thing and it is shape, not numbers:** gold runs from a host script, so the cell is not green *through Databricks Jobs*, which is what its name claims and what DoD 3 requires. That is G4 — `dbt_task` is unimplemented in the emulator. Everything else a ✅ needs, it has |
| Snowflake · Airflow 3 | `contoso-data-product-snowflake-airflow3` | `snowflake-platform-airflow3` | ⬜ | Snowflake has no bronze or silver yet |
| Snowflake · Tasks | `contoso-data-product-snowflake-tasks` | `snowflake-platform-tasks` | 🔴 | gold-only over an empty seeded silver; emulator has no Tasks. ~~Also fails DoD 1~~ — **DoD 1 now met**: both `snowflake-target` and `contoso-data-product` moved from sibling paths to published wheels, so the repo clones and builds alone, and it is pinned to core **v0.2.0** at last. Two tests hold it |

`contoso-sources` is **published**: <https://github.com/calvinchengx/contoso-sources> (Apache 2.0, `_data/` materialised not committed). G10 closed.

**A decision was taken here, and it changes what a green family means.** The
Databricks cell builds gold correctly — its aggregates are identical to
Fabric's to the last decimal place — but two of its own contracts fail on an
emulator defect (G8), and `gold.py` refused to publish a snapshot for a table
that breaks its contract. Both behaviours were correct; together they removed
the cell from the comparison the family exists to make.

**Chosen: separate recording a measurement from asserting a pass.** `gold.py`
writes the snapshot **and then** exits non-zero. The snapshot carries a
`contract_failures` field naming each failing contract in dbt's own words, with
an optional platform-supplied `cause`. `compare_products` compares the
aggregates as normal, and exits **non-zero** when any snapshot carries
failures, while still printing the agreement it found.

Why, in one line: evidence is worth recording even when the run that produced
it failed — and what must never happen is evidence recorded *without* the
failure attached, which is exactly the stale snapshot this platform once
published, silently outliving its own fix.

The options not taken, kept because the reasoning matters:

| | option | verdict |
|---|---|---|
| 1 | **Leave it** — no snapshot while G8 is open. | Honest, and it costs the cell its place in the comparison. |
| 2 | ~~**Name it with `dialect_gap`**~~ | **Does not work — checked, not assumed.** For the optional runtimes `dialect_gap` skips comparison entirely, but Databricks is half of the REQUIRED pair: there it only exempts the snapshot from `empty()`, and the aggregates are compared anyway. It would exempt nothing that matters while permanently disarming the one guard that catches a genuine future zero. Its stated meaning — "this runtime genuinely cannot build gold" — is also false here. |
| 3 | **Cast the aggregates in shared gold SQL.** | Green everywhere, and it hides an emulator defect inside product code. |

Two traps this surfaced, both worth keeping:

- **`ABSENT` beats `[]`.** An always-present empty list makes "this runtime
  evaluated its contracts and they passed" indistinguishable from "it never
  checked".
- **dbt overwrites `run_results.json` every invocation**, and `dbt run` shares
  the target directory. Read without checking, it reports the *models*: nine
  rows, zero failures. Believed, that publishes a snapshot asserting no
  contract failures on a run where two failed — the precise false green this
  design exists to prevent. Assert `args.which == "test"` first.

**A green that names no image is not a green.** The Databricks cell currently
passes every contract, and the three-way comparison exits 0 — against a
locally built `databricks-emulator:g8fix-local` that has never been pushed
(`docker image inspect --format '{{.RepoDigests}}'` → `[]`) while `versions.env`
pins `0.2.4`. The measurement is real and the fix is real; the *claim* "the cell
is green" is not, because no one else can reproduce it. This is G11's shape one
tier up — a change that never ships reaches no consumer — and the family's own
discipline is that a green run says which images it verified.

The sequence that turned it into a reproducible claim — **all of it done**:

1. ~~Merge [databricks-emulator#47](https://github.com/calvinchengx/databricks-emulator/pull/47).~~ Merged, `1a4c0ce`.
2. ~~Cut a `databricks-emulator` release.~~ **v0.2.5**, image published and pullable.
3. ~~Bump `versions.env` in `databricks-platform-jobs`.~~ [#10](https://github.com/calvinchengx/databricks-platform-jobs/pull/10).
4. ~~Re-run `make verify` against the **released** image.~~ `PASS=52 ERROR=0`, exit 0,
   three-way `compare_products` exit 0 — on `ghcr.io/…/databricks-emulator:0.2.5`.
5. ✅ **on this axis.** The cell is still 🟡 for a different reason: DoD 3, gold
   runs from a host script rather than through Databricks Jobs (G4). Worth
   keeping the two apart — "we cannot reproduce this" is a different complaint
   from "this is not the orchestrator we named", and only the first is closed.

A NOTE ON HOW THE LAST STEP NEARLY PASSED WRONGLY. Bumping `versions.env` does
not restart a running stack: the file said `0.2.5` while the container was
still the local build, and the two images have different digests and different
layers. A re-verify that skipped `docker compose up` would have reported green
for the released image while never having run it — the same defect as a green
that names no image, one level subtler. Check the image the containers are
ACTUALLY running, not the pin.

## The gaps, and who owns each

Every empty or amber cell is blocked on one or more of these. A gap is named
here so that it is a line item, not a surprise.

| # | gap | blocks | owner | shape of the fix |
|---|---|---|---|---|
| G1 | **Two silvers — PARTIALLY CLOSED.** The dbt silver project is now canonical in core (**v0.2.0**, `silver_dir()` beside `gold_dir()`), and the Fabric Airflow 3 leaf consumes it and carries no copy. **Still open:** (a) `run_silver` (PySpark) is still a SECOND DEFINITION rather than a runner over those models — the "PySpark executes the same SQL" half is not done; (b) **bronze is duplicated too**, which was not in the original framing — core's `run_bronze` (Spark) and the leaf's `bronze.py` (delta-rs) parse and name independently. Two *writers* is legitimate; an Airflow worker has no Spark session. Two *definitions* of the parse rules and table names is not; (c) no silver-metrics equality test exists yet, and one known divergence has to be encoded rather than asserted away: the dbt `silver_customers` names 6 columns where the PySpark one carries all ~101, so `customer_columns` is 101 vs 6 **by design**. | everything | core | finish (a)–(c) |
| G2 | **Two repos contain their product.** `fabric-platform-notebook-pipelines` and `databricks-platform-jobs` hold ingest, notebooks, bronze/silver/gold runners. | those two cells being honest | platform + leaf | split: platform keeps compose/provision/vendors/target; the rest becomes the leaf |
| G3 | **Airflow 2.10.5 ≠ Airflow 3.3.1.** Task SDK vs `airflow.decorators`; `Asset` vs `Dataset`; api-server execution vs direct import; DAG bundle vs OneLake sync. | Fabric · built-in Airflow | leaf | a second DAG in the 2.x idiom, in its own leaf; cosmos pinned to a 2.10-compatible release |
| G4 | **`dbt_task` not implemented**, and the statement agent is not a shell. Gold runs from the host today. | Databricks · Jobs | **databricks-emulator** | implement `dbt_task` (agent image carries `dbt-databricks`, runs against the warehouse endpoint) — real Databricks has it natively |
| G5 | **Snowflake has no bronze or silver.** The platform seeds empty tables and gold reports a `dialect_gap`. | both Snowflake cells | core + leaf | SQL bronze (`COPY INTO` from a stage) and dbt-snowflake silver; a build, not a port |
| G6 | **Snowflake Tasks not implemented** in the emulator (`parity.md`: 🔴). | Snowflake · Tasks | **snowflake-emulator** | `CREATE TASK … AFTER … AS …` and task graphs |
| G7 | **`money_is_never_stored_as_float` read SQL Server's `INFORMATION_SCHEMA`.** Empty in Unity Catalog, so it passed vacuously on Databricks — while that engine's money columns read as `double`. **Fixed and released** in core **v0.1.1**: `macros/reflect.sql` (`INFORMATION_SCHEMA` on Fabric, `DESCRIBE TABLE` on Spark engines) and the contract rewritten over it. **Witnessed on Databricks**: `PASS=50 ERROR=2`, and it caught **12** genuinely-float money columns across all five gold models — the red predicted here, for the reason predicted. | contract honesty | core | witness on Fabric; Snowflake once G5 lands. Stays red on Databricks until G8 is fixed upstream. |
| G8 | ~~OPEN~~ **CLOSED — fixed, released and WITNESSED ON THE RELEASED IMAGE.** `make verify` on a clean stack against `ghcr.io/calvinchengx/databricks-emulator:0.2.5` (pulled, not built locally) reports `PASS=52 WARN=0 ERROR=0` with `money_is_never_stored_as_float` among the passes, and the gold star's Delta log now holds `decimal(19,4)` / `decimal(29,4)` where it held `double`. `KNOWN_CAUSES` in `gold.py` is emptied in the same change that made it false (`databricks-platform-jobs` `fc1704c`). Released in databricks-emulator **v0.2.5** ([#47](https://github.com/calvinchengx/databricks-emulator/pull/47), notes in `docs/release-notes/v0.2.5.md`). The consumer's pin moves in [databricks-platform-jobs#10](https://github.com/calvinchengx/databricks-platform-jobs/pull/10), by hand — see G16 for why nothing dispatched. The root cause is not the DOUBLE mapping — that was a symptom of registering column metadata into UC **at all**. Measured four ways over the same Delta bytes: no columns → Sail reads the Delta log and gets `decimal(19,4)`; DOUBLE columns → Sail binds the column as double; `decimal(19,4)` columns → Sail refuses (`Unsupported complex type`); a `_col` placeholder → the table is unreadable. The fix registers no columns and lets the Delta log be the schema, which it already was. Originally reported here as **Decimal columns register in UC as `DOUBLE`, so they are read as float** — `databricks-emulator` `internal/sqlshim/shim.go` (`sparkToUC`) deliberately maps `decimal(p,s)` to `type_name: DOUBLE`; the Delta log, the Parquet physical type and `DESCRIBE` all still say `decimal(19,4)`, but the planner trusts UC. **Not** a `sum()` defect — that was this plan's earlier reading and it is wrong: a fresh `CREATE TABLE t AS SELECT CAST(1.5 AS DECIMAL(19,4)) AS m` answers `typeof(sum(m))` with `decimal(29,4)`, correctly. | Databricks money columns; G7 staying red | **databricks-emulator** ([#46](https://github.com/calvinchengx/databricks-emulator/issues/46)) | the emulator maps it that way because Sail's unity provider rejects `decimal(p,s)` (`Unsupported complex type`), so the real fix is likely upstream in Sail. The databricks snapshot casts back to `DECIMAL(19,4)` in the engine meanwhile. |
| G9 | **Stale Spark Connect session never re-established** by the shared agent (`session … is not running`). `agent.py` calls `getOrCreate()` at module import and holds that one session for the life of the process, so a dropped session is permanent and no caller-side retry can help. Restarting the agent clears it. Bit us twice in one day, between silver and register. | any Sail-backed cell, intermittently | **fabric-emulator** ([#312](https://github.com/calvinchengx/fabric-emulator/issues/312)) | rebuild the session on session-not-found rather than treating `getOrCreate()` as an import-time constant |
| ~~G10~~ | ~~**`contoso-sources` unpublished.**~~ **Closed** — published Apache 2.0, `_data/` still materialised rather than committed. | — | — | — |
| G11 | **Core is consumed by tag, so nothing in it reaches a cell without a release.** v0.1.1 shipped G7's fix; the plan had no step that says so, and a core commit that is never released is invisible to every consumer. | every cell, silently | core | tag `v*` → the release workflow builds and attaches the wheel; then bump each consumer's pin and relock. Four consumers, all pinned as of today: three by wheel URL and one by git tag. `snowflake-platform-tasks` was the exception — it pinned core by **sibling path**, so it could not be cloned alone and no release could reach it; v0.1.1 and v0.2.0 both went past it silently. Fixed. **v0.2.0 exercised the rule for the first time**: the leaf's tests failed with `ImportError` on `silver_dir` until core was released and the pin bumped. It works. **The rule has a second failure mode, found at databricks-emulator v0.2.5 and recorded as G16**: releasing is not enough if the thing that tells the consumer cannot fire, and unlike the `ImportError` above, that one fails SILENTLY — the consumer keeps passing on the old pin. |
| G12 | **The ERP password is the one fixture credential written into tracked files.** The vendor API keys get this right: `_data/**/.api-key` is gitignored and written at `make sources` from the generator (`materialise_sources.py`), so the value is knowable but never committed. `contoso-erp-dev` is not — and it is worse than a single declaration in `sources.yaml`, because each platform generator carries it as a **fallback default** (`v.get("db_password", "contoso-erp-dev")`). Rotating the declaration would leave stale defaults in three platform repos that keep working, so nothing would fail to tell you. | nothing — it guards a throwaway container and is public by construction | `contoso-sources` + every platform generator | generate it at `make up` and write it where both the compose env and the connector config read it, the `.api-key` pattern. **Not a history rewrite**: the value has to be knowable, it is already in four public repos including a tag consumers pin, and rotating forward is the proportionate response |
| ~~G13~~ | ~~**One platform carries its own copy of the vendors.**~~ **Closed.** `fabric-platform-notebook-pipelines` now generates its vendor stack from `contoso-sources/sources.yaml` and tracks no vendor definition. Per-vendor tuning moved into the declaration (`health`, `memory`, `mem_limit`) because a budget sized to a 95 MB export is a fact about the vendor; the generated fragment reproduces the old file's ports and limits exactly. The 13 vendor invariants moved to `contoso-sources`, which now has a test suite; the 3 that assert a consumer's parsing DDL stayed with that DDL. | — | — | — |
| G14 | **Core silver uses Spark-SQL constructs.** `lateral view explode`, `posexplode`, `date_add`, `datediff` — fine on dbt-fabricspark and dbt-databricks, and they will NOT run on Snowflake or a Fabric Warehouse without dialect macros. Stated in core's `dbt_project.yml` header, so it is not hidden, but it belongs here. Overlaps G5 and is distinct from it: G5 is the missing layer, this is the SQL. | Snowflake cells | core | dialect macros, the `flag`/`date_quarter`/`varchar_n` pattern already in gold |
| ~~G15~~ | ~~**The two runtimes publish the product under DIFFERENT domains.**~~ **Closed.** `contoso-commerce` wins; `fabric-platform-notebook-pipelines` imports `DOMAIN` from core and no longer names its own (`6a1a75c`). `GLOSSARY` and the domain's `displayName` follow it — GLOSSARY stays local because core does not name it and the Databricks runtime publishes no glossary at all, but its value has to track the domain or the catalog reads as two things again. A test fails on either half of the breach: a local `DOMAIN` assignment, or the import going missing. | — | — | **Residual, deliberately not folded in:** the two platforms still PUT the same domain with different `description`s, so the last runtime to run wins that field. And fabric publishes a `dataProducts` entity named `contoso-sales-star` that Databricks does not publish at all, while core names the product `contoso-analytics`. Neither is a two-domains bug; both are core-naming questions |
| G16 | **The Databricks release cannot tell its consumer.** `databricks-emulator`'s `release.yml` fires the acceptance `repository_dispatch` only when `ACCEPTANCE_DISPATCH_TOKEN` is set, and that repository has **no secrets at all** (`gh secret list` is empty; `fabric-emulator` has the token, dated 2026-08-03). So the step logs a warning and exits 0. Its warning is itself wrong: it says the consumer's daily cron still verifies the pin, but on a `schedule` run `github.event_name` is not `repository_dispatch`, so BOTH the step that moves the pin and the step that adopts it are skipped — the cron verifies whatever is already pinned and never moves it. v0.2.5 would have sat unconsumed indefinitely with every workflow green. Found while bumping 0.2.4 → 0.2.5; that bump is hand-written as a result. | every databricks-emulator release reaching its consumer, silently | **owner: a human** — needs a PAT with `contents:write` on `calvinchengx/databricks-platform-jobs`, which no agent can mint | add `ACCEPTANCE_DISPATCH_TOKEN` to `databricks-emulator`. The adopt path itself is now safe to trust: [databricks-platform-jobs#9](https://github.com/calvinchengx/databricks-platform-jobs/pull/9) made it move `versions.env`, `pyproject.toml` and `uv.lock` together, where before it committed only the first — and because every target runs `uv run --frozen`, which reads `uv.lock` and never `pyproject.toml`, the dispatch would have verified the NEW image against the OLD client and passed. Fix the warning's text too. |
| G17 | **The emulator's built-in Airflow runs `SequentialExecutor`; real Fabric runs `CeleryExecutor` and forbids changing it.** `fabric-emulator`'s profile-gated sidecar sets `AIRFLOW__CORE__EXECUTOR: SequentialExecutor` over sqlite (`docker-compose.yml`, and the same in `e2e/airflow/docker-compose.yml`). Microsoft's docs give the Fabric default as `CeleryExecutor` and list `AIRFLOW__CORE__EXECUTOR` among the configurations a user **cannot override** — so on real Fabric it is *always* Celery and a DAG author has no way to change it. Sequential runs ONE TASK AT A TIME, so the Contoso DAG's four parallel vendor ingests and seven concurrent silver models would serialise: the run would pass while demonstrating behaviour no Fabric user can have. A witness DAG of one task cannot see this, which is why the existing e2e is green. **Version parity itself is already exact** and was checked rather than assumed: Fabric supports Airflow **2.10.5** on Python **3.12** ([concepts](https://learn.microsoft.com/en-us/fabric/data-factory/apache-airflow-jobs-concepts), docs updated 2026-06), and the emulator runs `apache/airflow:2.10.5-python3.12`. No Airflow 3.x in Fabric and none announced. Two smaller drifts alongside it: Fabric defaults `DAGS_ARE_PAUSED_AT_CREATION` to **False** where the e2e sets `"true"`, and `DAG_DIR_LIST_INTERVAL` to **5**. | Fabric · built-in Airflow being a fair demonstration rather than merely green | **fabric-emulator** | give the sidecar `CeleryExecutor` with a real metadata DB and broker, as the family's other Airflow stack already has; align the two defaults above. Then a parallel DAG proves parallelism instead of hiding its absence |

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
