"""What bronze must contain, so a platform can check its own before silver runs.

BRONZE IS A CONTRACT, and `silver/models/sources.yml` has said so in prose for
as long as it has existed: a platform writes bronze in whatever technology it
has -- Spark on a Fabric notebook, delta-rs in an Airflow worker, COPY INTO on
Snowflake -- and "whatever a platform calls these, the columns silver reads
must be there".

Nothing checked it. On 2026-08-19 the Snowflake platform's bronze landed its
CSV feeds parsed (102,000 rows across 101 columns) and its JSON feeds whole,
in a single `doc` column. Silver then failed four layers away, inside a model,
with a message about a column it could not bind:

    Binder Error: Table "o" does not have a column named "lines"
    Candidate bindings: "doc"

That is a breach of a stated contract reported as a SQL error, at the wrong
layer, long after the step that caused it said it had succeeded. A contract
nothing verifies is the suggestion its own comment warns about.

So the declaration moved from prose into `sources.yml` as dbt `columns:`, and
this module reads it back. A platform calls `check_bronze` with whatever it
can learn about its own tables and finds out at BRONZE time, in bronze's own
words.
"""

from __future__ import annotations

import re
from pathlib import Path


def _sources_yml() -> str:
    return (Path(__file__).resolve().parent / "silver" / "models" / "sources.yml").read_text(
        encoding="utf-8"
    )


def bronze_contract() -> dict[str, list[str]]:
    """The columns silver reads, per bronze table, keyed by the table's `var` name.

    Parsed rather than imported from a YAML library, because this package has
    no runtime dependencies at all -- it installs into a Fabric notebook, a
    Databricks job cluster and a laptop, and anything it dragged in becomes
    something all three must agree about.
    """
    out: dict[str, list[str]] = {}
    current: str | None = None
    for line in _sources_yml().splitlines():
        table = re.match(r"^\s*- name: \"\{\{ var\('([a-z_]+)'\) \}\}\"\s*$", line)
        if table:
            current = table.group(1)
            out[current] = []
            continue
        if current is None:
            continue
        column = re.match(r"^\s+- name: ([a-z_][a-z0-9_]*)\s*$", line)
        if column:
            out[current].append(column.group(1))
        elif re.match(r"^\s*- name:", line):
            current = None
    return {k: v for k, v in out.items() if v}


def check_bronze(observed: dict[str, list[str]]) -> list[str]:
    """Compare a platform's bronze against the contract.

    `observed` maps the contract's var name to the columns that platform's
    table actually has -- read from the engine, not from the code that wrote
    it, because the question is what landed rather than what was intended.

    Returns one complaint per breach, empty when bronze holds. EXTRA COLUMNS
    ARE FINE and deliberately so: bronze is allowed to carry more than silver
    reads -- `bronze_pos_customers` has 101 columns and silver reads six --
    and a contract that forbade that would make every vendor's new field a
    breaking change.
    """
    problems = []
    for table, required in sorted(bronze_contract().items()):
        if table not in observed:
            problems.append(f"{table}: not present in bronze")
            continue
        have = {c.lower() for c in observed[table]}
        missing = [c for c in required if c.lower() not in have]
        if missing:
            problems.append(
                f"{table}: missing {', '.join(missing)} "
                f"(has {', '.join(sorted(have)) if have else 'nothing'})"
            )
    return problems
