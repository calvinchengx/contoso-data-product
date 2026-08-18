-- No money column may be a binary float. Checked against the WAREHOUSE'S OWN
-- catalog, because no amount of row checking can see this.
--
-- WHY THIS TEST EXISTS. `dim_product` unions the published catalogue with the
-- SKUs nobody published, and the unpublished side declared its price as
-- `cast(null as float)`. A UNION takes the wider type, so one `float` on a
-- column of NULLs silently demoted every real price back to floating point.
-- Every row still held the right number, every other test passed, and the
-- column had stopped being money. It was found by reading the reflected type,
-- which is the only thing that can find it.
--
-- MATCHED BY NAME, deliberately. A test listing the columns it knows about
-- protects the columns it knows about; the next money column somebody adds is
-- exactly the one that would slip through. Anything named like money has to BE
-- money, and a column that trips this and is genuinely not money should be
-- renamed rather than exempted.
--
-- REFLECTED THROUGH `reflected_columns`, NOT THROUGH ONE WAREHOUSE'S VIEWS.
-- This test used to read `INFORMATION_SCHEMA.COLUMNS` in uppercase T-SQL,
-- which is correct for a Fabric Warehouse and meaningless everywhere else. On
-- Databricks over Unity Catalog that view is EMPTY, so the test did not merely
-- pass vacuously -- it returned no rows at all and dbt reported `Internal
-- Error: Returned 0 rows, but expected 1 row`. A contract that cannot run on a
-- runtime is not protecting that runtime, and that runtime had a real float
-- for it to catch: its `sum()` over a decimal column returns `double`, so
-- every aggregate in fct_revenue_summary had stopped being money.
--
-- The macro holds the per-warehouse spelling, and says why it is not simply
-- `adapter.get_columns_in_relation` -- which is the right API and is currently
-- unusable against this family's emulator. See macros/reflect.sql.
--
-- NARROWER THAN IT WAS, and said out loud rather than left to be discovered.
-- The old query filtered no table at all, so it swept every table the
-- warehouse's catalog exposed; this reflects the five gold models named below
-- and nothing else. That is the price of reflecting per relation, and it is
-- paid knowingly: those five are what gold publishes, a `ref()` is what makes
-- the ordering correct, and a money column reaching gold through silver is
-- caught here at the boundary that matters. Add a model to the list when gold
-- gains one -- the list is the coverage.
--
-- ORDERING IS LOAD-BEARING, and this test did not always have it. A singular
-- test that names no model has no place in dbt's graph, so it gets scheduled
-- arbitrarily -- this one ran 4th of 61, BEFORE the models it checks were
-- rebuilt, and passed against the previous run's tables. It reported green
-- while a float was reintroduced, which is the precise failure it exists to
-- prevent, one level up.
--
-- The `ref()` calls below are what fix that, and they are deliberately OUTSIDE
-- the `execute` guard: dbt captures dependencies while PARSING, when `execute`
-- is false, so a ref reached only at run time registers no edge at all and the
-- ordering bug comes straight back.
{% set relations = [
    ref('dim_product'),
    ref('fct_sales'),
    ref('fct_orders'),
    ref('fct_revenue_summary'),
    ref('fct_daily_revenue')
] %}

-- Substrings, not a column list -- see MATCHED BY NAME above.
{% set money_like = ['amount', 'price', 'revenue', 'rate_to'] %}

-- What money is allowed to be. Exact, base-10, fixed scale. Spelt as prefixes
-- because adapters report the width differently: `decimal` from a Fabric
-- Warehouse, `decimal(19,4)` from Databricks.
{% set exact_numeric = ['decimal', 'numeric'] %}

{% set offenders = [] %}
{% if execute %}
  {% for relation in relations %}
    {% for column in reflected_columns(relation) %}
      {% set column_name = column.name | lower %}
      {% set data_type = column.type %}
      {% set named_like_money = namespace(yes=false) %}
      {% for fragment in money_like %}
        {% if fragment in column_name %}
          {% set named_like_money.yes = true %}
        {% endif %}
      {% endfor %}
      {% set is_exact = namespace(yes=false) %}
      {% for allowed in exact_numeric %}
        {% if data_type.startswith(allowed) %}
          {% set is_exact.yes = true %}
        {% endif %}
      {% endfor %}
      {% if named_like_money.yes and not is_exact.yes %}
        {% do offenders.append({
            'table': relation.identifier,
            'column': column.name,
            'type': data_type}) %}
      {% endif %}
    {% endfor %}
  {% endfor %}
{% endif %}

-- A SENTINEL ROW THAT IS ALWAYS FILTERED OUT, so the shape of the query does
-- not change with the number of offenders. `select ... union all select ...`
-- with no FROM is the one construct every target here agrees on; an empty
-- `values` list is not, and a bare `select ... where 1=0` needs a FROM on some
-- of them.
select table_name, column_name, data_type
from (
    select 'sentinel' as table_name, '' as column_name, '' as data_type
    {%- for offender in offenders %}
    union all select '{{ offender.table }}', '{{ offender.column }}', '{{ offender.type }}'
    {%- endfor %}
) as reflected_money_columns
where table_name <> 'sentinel'
