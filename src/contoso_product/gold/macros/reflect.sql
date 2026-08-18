{#-
  READ A BUILT TABLE'S COLUMN TYPES, on whichever warehouse is under us.

  Type is the one property no row check can see: every value in a column can be
  correct while the column has stopped being the thing it claims to be. So the
  float contract has to ask the CATALOG, and asking the catalog is the one
  thing dbt does not give a single portable spelling for.

  WHY NOT `adapter.get_columns_in_relation`, which is exactly that spelling.
  It was the first implementation here and it does not survive contact with
  this family's emulator. dbt-databricks 1.12.4 decides how to reflect from the
  compute's capabilities, and its rule for a SQL warehouse is unconditional:

      if self.is_sql_warehouse:
          ...
          return True          # dbr_capabilities.py -- no version check at all

  Against real Databricks that is fair, because a SQL warehouse is kept
  current. Against an emulator it is an assumption, and it makes dbt issue
  `DESCRIBE TABLE EXTENDED <t> AS JSON` -- which the Sail engine cannot parse:

      IllegalArgumentException: found JSON at 367:371 expected '.', ';', or
      end of input

  The engine parses `DESCRIBE TABLE EXTENDED <t>` and then meets `AS JSON`. So
  the portable API is unusable here until the emulator either supports that
  form or stops advertising a SQL warehouse's capabilities wholesale. Reported
  as a gap rather than worked around silently -- and when it closes, this macro
  collapses back to one adapter call.

  Two branches, in ONE place, so a contract can stay declarative. Both return
  the same shape: a list of {'name': ..., 'type': ...}, types lowercased.
-#}
{% macro reflected_columns(relation) %}
  {% if not execute %}
    {{ return([]) }}
  {% endif %}

  {%- if target.type in ['fabric', 'sqlserver', 'synapse'] -%}
    {#-
      UPPERCASE, because a Fabric Warehouse is case-sensitive. It reports
      `Latin1_General_100_BIN2_UTF8`, Microsoft's "default - case-sensitive
      (CS)" collation, so `information_schema.columns` is a different name from
      the view that exists and the tenant answers `Invalid object name`. This
      read lowercase and passed for months against an emulator whose databases
      inherited the container's case-INsensitive collation; it would have
      failed the first time it ran anywhere real.
    -#}
    {% set sql %}
      select COLUMN_NAME, DATA_TYPE
      from INFORMATION_SCHEMA.COLUMNS
      where TABLE_NAME = '{{ relation.identifier }}'
    {% endset %}
    {% set rows = run_query(sql) %}
    {% set out = [] %}
    {% for row in rows %}
      {% do out.append({'name': row[0], 'type': (row[1] | string | lower)}) %}
    {% endfor %}
    {{ return(out) }}
  {%- else -%}
    {#-
      `DESCRIBE TABLE`, which every Spark-family engine answers in the same
      three columns (col_name, data_type, comment) -- and which this emulator
      does support, unlike the `EXTENDED ... AS JSON` form above.

      DESCRIBE also appends partition and metadata sections, introduced by a
      row whose col_name starts with `#` or is blank. Reading past that would
      collect `# Partition Information` as a column named `#` -- harmless here
      only because nothing is named like money, which is not a guarantee worth
      relying on.
    -#}
    {% set rows = run_query('describe table ' ~ relation.render()) %}
    {% set out = [] %}
    {% for row in rows %}
      {% set col = row[0] | string %}
      {% if col.strip() and not col.startswith('#') %}
        {% do out.append({'name': col, 'type': (row[1] | string | lower)}) %}
      {% endif %}
    {% endfor %}
    {{ return(out) }}
  {%- endif -%}
{% endmacro %}
