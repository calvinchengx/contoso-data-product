{#-
  THE THREE PLACES SILVER SPEAKS SPARK, and what each engine says instead.

  Silver is dbt SQL so that every runtime builds the same models, and it very
  nearly does: six of the eight need no dialect work at all. Three constructs do
  -- an array explode, a day offset and a date series -- and they were written
  in Spark's spelling because Spark was the only engine when they were written.

  Kept as macros rather than per-engine copies of the models, for the reason the
  family's whole design rests on: a second copy of a model agrees with the first
  until the day one of them is fixed. A macro is one definition with a branch in
  it, and the branch is visible.

  The gold project already does this -- `flag`, `date_quarter`, `varchar_n`,
  `str_concat` -- so this is the established pattern, not a new one.
-#}

{#-
  Turn an array column into rows.

  Spark:     `lateral view explode(col) alias as item`  -- a clause
  Snowflake: `, lateral flatten(input => col) alias`    -- a join
  DuckDB:    `, unnest(col) as alias`

  `fields` NAMES THE ELEMENT'S COLUMNS, and it exists so the MODEL does not have
  to branch. Spark's `explode ... as line` binds `line` to the element itself,
  so `line.line_no` is a field of it. Snowflake's `flatten` binds `line` to a
  RELATION whose element is `line.value`, and reaching into it is `line.value:
  line_no` -- a different spelling in every reference, not just in the clause.
  Projecting the fields back to their Spark names inside the lateral means the
  five references in silver_web_order_lines are identical on every engine.

  AND THEIR TYPES WITH THEM. FLATTEN hands back VARIANT, so an unwrapped field
  is a document: `cast(quantity as int) * unit_price` becomes INTEGER times
  JSON and the engine refuses it. The model already knows what each field is --
  it casts them one line later -- so it says so here and the lateral casts once,
  where Spark's explode gives typed struct fields for free.

  Found the hard way: without this, `explode_array` fixed the FROM clause and
  left `cast(line.line_no as int)` untouched, so silver failed on Snowflake at
  the first column of the exploded row -- with the clause it had just been given
  looking correct.

  The whole clause is emitted, not just the function, because the three are not
  the same shape: Spark's LATERAL VIEW is its own syntax, and the others are
  table functions in the FROM list. A macro that returned only the function name
  would leave every caller to get the surrounding punctuation right per engine,
  which is exactly the duplication this avoids.
-#}
{% macro explode_array(col, alias, fields={}) -%}
  {%- if target.type in ['snowflake'] -%}
    , lateral (select
      {%- for f, ty in fields.items() %} v.value:{{ f }}::{{ ty }} as {{ f }}
      {{- "," if not loop.last }}{% endfor %}
      from lateral flatten(input => {{ col }}) v) {{ alias }}
  {%- elif target.type in ['duckdb'] -%}
    , unnest({{ col }}) as {{ alias }}
  {%- else -%}
    lateral view explode({{ col }}) exploded as {{ alias }}
  {%- endif -%}
{%- endmacro %}

{#-
  A date, n days on.

  Spark:     `date_add(d, n)`
  Snowflake: `dateadd(day, n, d)`
  T-SQL:     `dateadd(day, n, d)`
  DuckDB:    `d + n * interval 1 day`  -- its date_add takes an INTERVAL, so the
             two-argument Spark form silently means something else there, which
             is the kind of difference that produces wrong dates rather than an
             error.
-#}
{% macro date_offset(d, n) -%}
  {%- if target.type in ['snowflake', 'fabric', 'sqlserver', 'synapse'] -%}
    dateadd(day, {{ n }}, {{ d }})
  {%- elif target.type in ['duckdb'] -%}
    ({{ d }} + ({{ n }}) * interval 1 day)
  {%- else -%}
    date_add({{ d }}, {{ n }})
  {%- endif -%}
{%- endmacro %}

{#-
  Every date from `lo` to `hi` inclusive, one per row, as `rate_date`.

  This is the one that is genuinely different in kind. Spark has no generator,
  so the original built a string of spaces as long as the span and exploded it
  positionally -- ingenious, and unreadable anywhere else. Snowflake and DuckDB
  both have real generators and should use them.

  Emitted as a complete relation rather than an expression, because the Spark
  form needs a LATERAL VIEW against the bounds row and the others do not: there
  is no smaller piece the three have in common.
-#}
{% macro date_series(bounds, lo, hi) -%}
  {%- if target.type in ['snowflake'] -%}
    select {{ date_offset('b.' ~ lo, 'seq4()') }} as rate_date
    from {{ bounds }} b,
         table(generator(rowcount => 20000))
    where {{ date_offset('b.' ~ lo, 'seq4()') }} <= b.{{ hi }}
  {%- elif target.type in ['duckdb'] -%}
    select unnest(generate_series(b.{{ lo }}, b.{{ hi }}, interval 1 day))::date
             as rate_date
    from {{ bounds }} b
  {%- else -%}
    select {{ date_offset('b.' ~ lo, 'cast(s.pos as int)') }} as rate_date
    from {{ bounds }} b
    lateral view posexplode(split(space(datediff(b.{{ hi }}, b.{{ lo }})), ' ')) s as pos, val
  {%- endif -%}
{%- endmacro %}
