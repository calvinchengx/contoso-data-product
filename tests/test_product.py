"""The product package is importable and gold SQL has no dialect leaks."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from contoso_product import COUNTRY, MONEY, RATE, gold_dir
from contoso_product.contracts import METRICS, PRODUCT_NAME, schema_yml


def test_constants():
    assert MONEY == "decimal(19,4)"
    assert RATE == "decimal(19,6)"
    assert COUNTRY["USA"] == "US"
    assert PRODUCT_NAME == "contoso-analytics"
    assert "revenue_usd" in METRICS


def test_gold_layout():
    g = gold_dir()
    assert (g / "models" / "fct_revenue_summary.sql").is_file()
    assert (g / "models" / "fct_sales.sql").is_file()
    assert (g / "macros" / "flag.sql").is_file()
    assert schema_yml().is_file()


def test_no_t_sql_bit_in_models():
    models = Path(gold_dir() / "models")
    leaked = []
    for p in models.glob("*.sql"):
        text = p.read_text(encoding="utf-8")
        if "as bit" in text.lower():
            leaked.append(p.name)
    assert leaked == [], f"T-SQL BIT leaked into portable models: {leaked}"


def test_the_float_contract_reflects_on_every_target():
    """`money_is_never_stored_as_float` must run on every target, not one.

    It used to read `INFORMATION_SCHEMA.COLUMNS` in uppercase T-SQL -- correct
    for a Fabric Warehouse and meaningless elsewhere. On Databricks over Unity
    Catalog that view is empty, so the contract did not merely pass vacuously:
    it returned no rows and dbt reported `Internal Error: Returned 0 rows, but
    expected 1 row`. A contract that cannot run on a runtime protects nothing
    there, and that runtime had a genuine float for it to catch.
    """
    sql = (gold_dir() / "tests" / "money_is_never_stored_as_float.sql").read_text(
        encoding="utf-8"
    )
    assert "reflected_columns(" in sql, (
        "the float contract must reflect through the shared macro, which "
        "answers on every target, rather than one warehouse's catalog views"
    )
    # The COMMENTS name it -- they explain why it went. Only the executable
    # SQL is checked, or this test would fail on its own explanation.
    code = "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    )
    assert "INFORMATION_SCHEMA" not in code.upper(), (
        "a T-SQL catalog view is back in a contract that has to run on Spark too"
    )


def test_the_float_contract_registers_its_dependencies_at_parse_time():
    """The `ref()` calls must sit OUTSIDE the `execute` guard.

    dbt captures dependencies while PARSING, when `execute` is false. A ref
    reached only at run time registers no edge, the test loses its place in the
    graph, and it gets scheduled arbitrarily -- this one once ran 4th of 61,
    before the models it checks were rebuilt, and passed against the previous
    run's tables. It reported green while a float was reintroduced.
    """
    sql = (gold_dir() / "tests" / "money_is_never_stored_as_float.sql").read_text(
        encoding="utf-8"
    )
    guard = sql.index("{% if execute %}")
    refs = [i for i in range(len(sql)) if sql.startswith("ref(", i)]
    assert refs, "the contract names no models at all"
    assert all(i < guard for i in refs), (
        "a ref() sits inside the execute guard, so dbt will not see the "
        "dependency at parse time and the ordering bug comes back"
    )


def test_reflection_is_written_once_and_covers_both_dialect_families():
    """The per-warehouse spelling lives in ONE macro, not in each contract.

    `adapter.get_columns_in_relation` would be the single portable call and is
    what this should be. It is currently unusable against the family's
    Databricks emulator: dbt-databricks treats any SQL warehouse as fully
    capable (`if self.is_sql_warehouse: return True`, with no version check),
    so it issues `DESCRIBE TABLE EXTENDED <t> AS JSON`, and the Sail engine
    answers `found JSON ... expected '.', ';', or end of input`. The macro
    records that, so the workaround cannot outlive its reason unnoticed.
    """
    macro = (gold_dir() / "macros" / "reflect.sql").read_text(encoding="utf-8")
    assert "INFORMATION_SCHEMA.COLUMNS" in macro, "the T-SQL branch is missing"
    assert "describe table" in macro.lower(), "the Spark-family branch is missing"
    assert "get_columns_in_relation" in macro, (
        "the macro must name the portable API it is standing in for, and why"
    )


def test_money_is_matched_by_name_not_by_a_column_list():
    """Anything named like money has to BE money.

    A contract listing the columns it knows about protects the columns it knows
    about; the next money column somebody adds is exactly the one that slips
    through.
    """
    sql = (gold_dir() / "tests" / "money_is_never_stored_as_float.sql").read_text(
        encoding="utf-8"
    )
    for fragment in ("amount", "price", "revenue", "rate_to"):
        assert f"'{fragment}'" in sql, f"the contract stopped matching {fragment!r}"


def test_integer_division_is_never_left_to_the_dialect():
    """`/` means different things on T-SQL and Spark, so it may not decide a type.

    T-SQL divides two ints and gives an int; Spark's `/` is always double
    division. `fiscal_month_index / 3 + 1 as fiscal_quarter` therefore produced
    `1` on Fabric and `1.0` on Databricks from one shared model -- and the
    `accepted_values` test for [1, 2, 3, 4] failed on one runtime while passing
    on the other. Anywhere an integer is wanted out of a division, the cast has
    to be written down.
    """
    dim_date = (gold_dir() / "models" / "dim_date.sql").read_text(encoding="utf-8")
    code = "\n".join(
        line for line in dim_date.splitlines() if not line.lstrip().startswith("--")
    )
    for line in code.splitlines():
        if "/ 3" in line:
            assert "cast(" in line, (
                "an integer division is left to the dialect to type: " + line.strip()
            )


# --- RULES.md: what may and may not live in the core -------------------------
#
# The core is the one place the product is written. These four tests are the
# "enforced by" column of RULES.md; a rule that names a test which does not
# exist is unenforced with extra steps.

_CORE = Path(__file__).resolve().parents[1]
_SRC = _CORE / "src" / "contoso_product"


def _pyproject() -> str:
    return (_CORE / "pyproject.toml").read_text(encoding="utf-8")


def test_gold_project_is_complete():
    """Every gold model, macro and contract ships in the package.

    RULES.md §1: transform SQL and the contracts exist ONLY here. That is
    meaningless if a consumer has to reach for a file this package forgot to
    include -- so the wheel must carry the whole dbt project, and the five
    contract names every runtime's snapshot lists must be exactly the singular
    tests present.
    """
    g = gold_dir()
    assert (g / "dbt_project.yml").is_file()
    models = sorted(p.stem for p in (g / "models").glob("*.sql"))
    assert len(models) == 9, models
    contracts = sorted(p.stem for p in (g / "tests").glob("*.sql"))
    assert contracts == [
        "both_selling_systems_reach_the_pack",
        "every_country_resolves_to_the_dimension",
        "fiscal_year_is_not_the_calendar_year",
        "money_is_never_stored_as_float",
        "revenue_summary_loses_no_revenue",
    ], contracts


def test_no_runtime_dependencies():
    """RULES.md §1: this package drags nothing in.

    It must install into a Fabric notebook, a Databricks job cluster, a
    Snowflake procedure and a laptop, and anything it required would become
    something all of those have to agree about. Spark arrives from the caller.
    """
    text = _pyproject()
    m = re.search(r"^dependencies\s*=\s*\[(.*?)\]", text, re.DOTALL | re.MULTILINE)
    assert m, "pyproject.toml declares no [project] dependencies list at all"
    deps = [d.strip().strip('",\'') for d in m.group(1).splitlines() if d.strip().strip('",\'')]
    deps = [d for d in deps if not d.startswith("#")]
    assert deps == [], f"core must have no runtime dependencies, has: {deps}"


def test_no_engine_named_in_core():
    """RULES.md §1: nothing here opens a connection or names an endpoint.

    An engine host, a warehouse id or a credential in this package is a leaf's
    decision leaking upward -- and it would ship to every leaf at once.
    Comments and docstrings may DESCRIBE an engine (the dialect macros must);
    code may not ADDRESS one.
    """
    banned = ("localhost", "127.0.0.1", "azuredatabricks.net", "snowflakecomputing.com",
              "fabric.microsoft.com", "onelake.dfs", "http://", "https://")
    offenders = []
    for p in _SRC.rglob("*.py"):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                # A docstring is a Constant too; skip those that are the first
                # statement of a module/def/class body.
                for b in banned:
                    if b in node.value and not _is_docstring(tree, node):
                        offenders.append(f"{p.relative_to(_CORE)}: {b!r}")
    assert offenders == [], f"an engine address is written into core code: {offenders}"


def _is_docstring(tree: ast.AST, node: ast.Constant) -> bool:
    for parent in ast.walk(tree):
        body = getattr(parent, "body", None)
        if isinstance(body, list) and body:
            first = body[0]
            if isinstance(first, ast.Expr) and first.value is node:
                return True
    return False


def test_no_orchestrator_in_core():
    """RULES.md §2: no DAG, job spec, notebook or task graph lives here.

    Those are LEAF products, one per platform, in that platform's idiom. A
    runner in the core is the thing that would make the core unreadable to the
    team of any single platform -- and it would be the first step back toward
    "one repo with seven confusing configurations".
    """
    banned_imports = {"airflow", "cosmos", "databricks.sdk.service.jobs", "snowflake.snowpark"}
    banned_files = ("dags", "notebooks", "jobs.json", "job.yml", "tasks.sql")
    hits = []
    for p in _SRC.rglob("*"):
        if p.is_dir():
            continue
        rel = str(p.relative_to(_SRC))
        if any(rel == b or rel.startswith(b + "/") or rel.endswith(b) for b in banned_files):
            hits.append(rel)
        if p.suffix == ".py":
            for line in p.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if s.startswith(("import ", "from ")):
                    for b in banned_imports:
                        if s.startswith((f"import {b}", f"from {b}")):
                            hits.append(f"{rel}: {s}")
    assert hits == [], f"an orchestrator leaked into the core: {hits}"
