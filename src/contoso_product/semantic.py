"""The product's semantic model: one table, the family's measures, as data.

The family claim (docs/00-family.md) says the product is defined by its
outputs. The three numbers every cell must agree on — revenue_usd,
cancelled_revenue_usd, sale_lines — are all columns of ONE gold table,
`fct_revenue_summary`, so the model that serves them to a BI client is a
single Direct Lake table with three SUM measures and the slicer columns the
ODCS contracts already name. Deliberately no dims and no relationships: the
summary carries its segments denormalised, and a model wider than what the
family compares would be surface nobody's contract stands behind.

WHAT LIVES HERE AND WHAT MAY NOT, and both follow from tested rules:

- Columns are declared once, in `gold/models/schema.yml` — the same "one
  definition of quality" the ODCS contracts derive from. This module restates
  the NAMES because it must attach types, and `test_semantic_columns_come_from_
  the_gold_schema` fails if the two ever differ. It cannot read the yml at
  runtime: core has no runtime dependencies (`test_no_runtime_dependencies`),
  and a yaml parser would be one.

- The Direct Lake BINDING — the OneLake URL, the warehouse it points at, the
  schema gold landed in — is the CALLER's to supply. Core code may not address
  an engine (`test_no_engine_named_in_core` bans the URL constants outright),
  and the binding is a deployment fact exactly the way a dbt profile is: the
  same model definition deploys against the emulator and against real Fabric,
  differing only in the expression the leaf passes to `model_bim`.

- Expected values are not written here or anywhere (RULES.md §2): a cell's
  semantic contract asserts the measures against THE RUN'S OWN SNAPSHOT, so a
  model that disagrees with what the pipeline just published fails even when
  both are wrong about the world.
"""

from __future__ import annotations

from decimal import Decimal

from .contracts import PRODUCT_NAME

# The one table the model serves, named exactly as gold builds it.
TABLE = "fct_revenue_summary"

# (name, tabular data type). Names must match gold/models/schema.yml's
# declared columns for TABLE — enforced by test, see the module docstring.
# Types are declared here and only here: the yml carries quality contracts,
# not storage types, and a semantic model needs both.
COLUMNS: tuple[tuple[str, str], ...] = (
    # MONEY IS `decimal`, NOT `double`, and the product's own contract says so:
    # `money_is_never_stored_as_float` requires every column named like money to
    # be an exact base-10 type in the warehouse, and it would be strange for the
    # model SERVING those columns to widen them back to a binary float on the
    # way out. That contract exists because a single `cast(null as float)` in a
    # UNION once demoted every real price silently -- every row still held the
    # right number and the column had stopped being money.
    #
    # It changes nothing against this family's emulator, whose evaluator sums in
    # float64 whatever a column declares -- checked, not assumed
    # (`summableType` and `daxDataType` both accept decimal and both land on
    # DOUBLE). On real Fabric the engine honours the declared type, so this is
    # the difference between a model that is correct where it is measured and
    # one that is correct where it is deployed.
    ("revenue_usd", "decimal"),
    ("sale_lines", "int64"),
    ("cancelled_revenue_usd", "decimal"),
    ("fiscal_year_label", "string"),
    ("customer_segment", "string"),
    ("product_segment", "string"),
    ("channel_system", "string"),
)

# Measure name -> DAX. SUM only, on purpose: every number the family compares
# is additive over the summary's grain, and each function used here must be
# one a bounded evaluator answers exactly or refuses — no APPROX*, no
# time-intelligence. test_measures_stay_inside_the_declared_dax names the
# allowlist so growing it is a reviewed decision, not a drive-by.
MEASURES: dict[str, str] = {
    "Revenue USD": f"SUM({TABLE}[revenue_usd])",
    "Cancelled Revenue USD": f"SUM({TABLE}[cancelled_revenue_usd])",
    "Sale Lines": f"SUM({TABLE}[sale_lines])",
}

# Which snapshot key each measure must equal. The snapshot is the pipeline's
# own published verdict (product_snapshot.json), so this mapping is what makes
# the semantic model a CONTRACT rather than a second source of numbers.
_MEASURE_SNAPSHOT_KEYS: dict[str, str] = {
    "Revenue USD": "revenue_usd",
    "Cancelled Revenue USD": "cancelled_revenue_usd",
    "Sale Lines": "sale_lines",
}


def expected_measures(snapshot: dict) -> dict[str, Decimal]:
    """What each measure must evaluate to, given the run's own snapshot.

    Decimal, not float: snapshot values are fixed-point strings
    ("129341157.6700"), and the caller decides the comparison tolerance
    against whatever its query surface returns.

    A missing key raises rather than skipping the measure — a semantic
    contract that silently asserts fewer measures than the model ships is the
    family's recurring silent-drop shape (G29).
    """
    out: dict[str, Decimal] = {}
    for measure, key in _MEASURE_SNAPSHOT_KEYS.items():
        if key not in snapshot:
            raise KeyError(
                f"snapshot has no {key!r}, so the {measure!r} measure cannot "
                f"be asserted; refusing to assert a subset")
        out[measure] = Decimal(str(snapshot[key]))
    return out


def model_bim(expression: str, schema_name: str, *,
              model_name: str = PRODUCT_NAME) -> dict:
    """The deployable model definition, given the caller's Direct Lake binding.

    `expression` is the M expression naming where the warehouse lives — built
    by the LEAF, because core may not address an engine. `schema_name` is the
    schema gold landed in on that platform (`dbo` on a Fabric warehouse),
    which is a deployment fact for the same reason.

    compatibilityLevel 1604 is the floor for Direct Lake partitions; both the
    emulator and real Fabric refuse them below it.
    """
    expression = (expression or "").strip()
    schema_name = (schema_name or "").strip()
    if not expression:
        raise ValueError("a Direct Lake model needs the caller's binding "
                         "expression; core will not invent an endpoint")
    if not schema_name:
        raise ValueError(f"a Direct Lake entity needs the schema {TABLE} "
                         f"landed in; refusing to guess")
    return {
        "name": model_name,
        "compatibilityLevel": 1604,
        "model": {
            "expressions": [
                {"name": "DL_Source", "kind": "m", "expression": expression}],
            "tables": [{
                "name": TABLE,
                "columns": [
                    {"name": n, "dataType": t, "sourceColumn": n}
                    for n, t in COLUMNS],
                "measures": [
                    {"name": n, "expression": e}
                    for n, e in MEASURES.items()],
                "partitions": [{
                    "name": TABLE,
                    "mode": "directLake",
                    "source": {
                        "type": "entity",
                        "entityName": TABLE,
                        "schemaName": schema_name,
                        "expressionSource": "DL_Source",
                    },
                }],
            }],
        },
    }
