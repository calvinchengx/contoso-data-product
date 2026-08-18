"""Render the canonical silver models to executable SQL, without dbt.

WHY THIS EXISTS. Silver has one definition -- the dbt project under
`silver/` -- and two runners. Cells with dbt point it at `silver_dir()`. Cells
that have a Spark session and no dbt (a Fabric notebook, a Databricks
`spark_python_task`) cannot, and until now they ran `run_silver`, which was a
SECOND DEFINITION of the same layer written in PySpark. Two definitions agree
until they do not; the whole of G1 is that sentence. This module is what lets
the second runner execute the FIRST definition's SQL instead.

NO JINJA DEPENDENCY, deliberately. This package has no runtime dependencies at
all -- it has to install into a Fabric notebook, a Databricks job cluster and a
laptop, and anything it dragged in becomes something all of those must agree
about. The models use exactly six constructs, counted rather than assumed:

    config(...)                 8   dropped -- materialisation is the runner's
    source('bronze', var(...))  7   -> the platform's bronze table name
    money(col) / rate(col)      6   -> a cast
    ref('silver_x')             2   -> a silver table this run wrote
    conform_country(col)        1   -> the COUNTRY map as a CASE

So a purpose-built reader is cheaper than the dependency, exactly as the
platforms' `sources.yaml` readers are cheaper than PyYAML. It FAILS on anything
it does not recognise rather than passing it through: an unrendered `{{ ... }}`
reaching an engine is a syntax error three layers from its cause, and a
construct silently dropped is worse -- it would produce SQL that runs and
computes something else.
"""

from __future__ import annotations

import re

from .silver import COUNTRY, MONEY, RATE

# One expression per pair. Non-greedy up to the closing braces, because a model
# line can carry two of them.
TAG = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)

_CONFIG = re.compile(r"^config\(.*\)$", re.DOTALL)
_SOURCE = re.compile(r"^source\(\s*'(?P<src>[^']*)'\s*,\s*var\(\s*'(?P<var>[^']*)'\s*\)\s*\)$", re.DOTALL)
_SOURCE_LITERAL = re.compile(r"^source\(\s*'(?P<src>[^']*)'\s*,\s*'(?P<name>[^']*)'\s*\)$", re.DOTALL)
_REF = re.compile(r"^ref\(\s*'(?P<name>[^']*)'\s*\)$", re.DOTALL)
_MONEY = re.compile(r"^money\(\s*'(?P<col>.*)'\s*\)$", re.DOTALL)
_RATE = re.compile(r"^rate\(\s*'(?P<col>.*)'\s*\)$", re.DOTALL)
_CONFORM = re.compile(r"^conform_country\(\s*'(?P<col>.*)'\s*\)$", re.DOTALL)


def conform_country_sql(col: str) -> str:
    """The COUNTRY map as a CASE, from the SAME dict `run_silver` conforms with.

    This is the one place the Python and dbt sides of the map can be made to
    agree by construction rather than by a test: the dbt project reads its
    `country_variants` var and this reads `COUNTRY`, and
    `test_country_map_is_not_duplicated_by_accident` holds those two equal. So
    a model rendered here conforms exactly as the same model does under dbt.
    """
    whens = "\n      ".join(
        f"when '{variant}' then '{canonical}'" for variant, canonical in COUNTRY.items()
    )
    return (
        f"coalesce(\n    case upper(trim({col}))\n      {whens}\n    end,\n"
        f"    upper(trim({col}))\n  )"
    )


def render(sql: str, *, sources: dict[str, str], refs: dict[str, str]) -> str:
    """One model's SQL, with every construct resolved.

    `sources` maps the declaration's var name to the table this platform
    actually called it -- the same indirection `dbt_project.yml` declares,
    because the platforms genuinely disagree (`bronze_customers` here,
    `bronze_pos_customers` in the Fabric Airflow cell). `refs` maps a silver
    model name to wherever this runner just wrote it.
    """
    unknown: list[str] = []

    def resolve(match: re.Match) -> str:
        body = match.group(1).strip()
        if _CONFIG.match(body):
            return ""
        m = _SOURCE.match(body)
        if m:
            name = sources.get(m.group("var"))
            if name is None:
                unknown.append(f"no bronze table bound for var {m.group('var')!r}")
                return match.group(0)
            return name
        m = _SOURCE_LITERAL.match(body)
        if m:
            name = sources.get(m.group("name"), m.group("name"))
            return name
        m = _REF.match(body)
        if m:
            name = refs.get(m.group("name"))
            if name is None:
                unknown.append(f"no table bound for ref {m.group('name')!r}")
                return match.group(0)
            return name
        m = _MONEY.match(body)
        if m:
            return f"cast({m.group('col')} as {MONEY})"
        m = _RATE.match(body)
        if m:
            return f"cast({m.group('col')} as {RATE})"
        m = _CONFORM.match(body)
        if m:
            return conform_country_sql(m.group("col"))
        unknown.append(body)
        return match.group(0)

    out = TAG.sub(resolve, sql)
    if unknown:
        raise ValueError(
            "silver_sql cannot render these constructs, and will not guess: "
            + "; ".join(sorted(set(unknown)))
            + ". Add them here rather than letting an unrendered tag reach the "
            "engine, where it fails three layers from its cause."
        )
    return out


def model_order(models: dict[str, str]) -> list[str]:
    """Model names in an order where every `ref` is already written.

    Derived from the models themselves rather than listed, so a model added to
    the project tomorrow is ordered tomorrow. Only silver_party refs anything
    today; stating the order by hand would be a second place for the graph to
    live, which is the defect this whole layer is about.
    """
    deps = {
        name: set(re.findall(r"ref\(\s*'([^']*)'\s*\)", sql))
        for name, sql in models.items()
    }
    ordered: list[str] = []
    remaining = dict(deps)
    while remaining:
        ready = sorted(n for n, d in remaining.items() if not (d - set(ordered)))
        if not ready:
            raise ValueError(
                f"silver models have a dependency cycle or a ref to something "
                f"outside the project: {sorted(remaining)}"
            )
        ordered.extend(ready)
        for n in ready:
            remaining.pop(n)
    return ordered
