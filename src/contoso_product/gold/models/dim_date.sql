-- The fiscal calendar. CONTOSO'S FINANCIAL YEAR STARTS 1 APRIL.
--
-- WHY THIS TABLE EXISTS AT ALL: `order_date` is a date, and a date cannot say
-- which financial year it falls in. That mapping is a business convention, not
-- a property of the value, so it belongs in a dimension where it is stated once
-- and can be read — not repeated inside every measure that needs it.
--
-- FY27 RUNS 1 APR 2026 TO 31 MAR 2027, so July 2026 trading is FY27 Q2. Note
-- that this deliberately does NOT agree with the calendar year or quarter: the
-- whole reason to carry both is that management reporting uses one and
-- everything else uses the other, and a model that silently conflated them
-- would be wrong for three months of every year.
--
-- BUILT FROM THE FACTS, not from a generated spine. A conventional dim_date is
-- an independent calendar covering some wide range, which in T-SQL means a
-- numbers table or a recursive CTE — a dependency on warehouse features this
-- platform has not established. Projecting the distinct dates that actually
-- occur needs none of that and cannot drift from the facts it describes. The
-- cost is that a period with no trading has no row, which is the right
-- trade while every order falls inside a single month.
-- BUILT FROM THE UNIFIED FACT, not from the POS orders alone. The storefront's
-- timestamps carry real UTC offsets, so once they are honoured its sales reach
-- back to 30 June — which is FY27 Q1, a different fiscal quarter from the July
-- trading the shops report. A calendar built only from POS would have no row
-- for that day and would drop the sales that fall on it.
with days as (
    select distinct cast(order_date as date) as date_key
    from {{ ref('fct_sales') }}
),

parts as (
    select
        date_key,
        year(date_key)  as calendar_year,
        month(date_key) as calendar_month,
        -- April onwards belongs to the NEXT fiscal year, which is what makes
        -- FY27 contain most of calendar 2026.
        case
            when month(date_key) >= 4 then year(date_key) + 1
            else year(date_key)
        end as fiscal_year,
        -- Months since the start of the fiscal year, 0-based: April is 0.
        (month(date_key) - 4 + 12) % 12 as fiscal_month_index
    from days
)

select
    date_key,
    calendar_year,
    calendar_month,
    {{ date_quarter('date_key') }} as calendar_quarter,
    fiscal_year,
    -- FLOOR, BECAUSE `/` AND `cast(... as int)` BOTH DIFFER ACROSS ENGINES.
    --
    -- The division half was found first: T-SQL divides two ints and gives an
    -- int; Spark's `/` is always double division, so this column arrived as
    -- `fiscal_quarter` 1.0 rather than 1 on the Databricks runtime, and
    -- `accepted_values` for [1,2,3,4] failed there while passing on Fabric.
    --
    -- THE CAST HALF WAS FOUND WHEN A THIRD ENGINE ARRIVED, and the comment
    -- that used to sit here is why it took so long. It said truncation toward
    -- zero "is what both do" -- TRUE OF T-SQL AND SPARK, and it expired
    -- silently when Snowflake joined the family. Snowflake and duckdb ROUND a
    -- cast to integer; T-SQL and Spark TRUNCATE. Measured, both directions:
    --
    --     cast(2/3 as int)   ->  0 on T-SQL,  1 on duckdb/Snowflake
    --     cast(floor(2/3) as int) -> 0 on both
    --
    -- June is fiscal_month_index 2, so rounding put it in Q2 with July instead
    -- of Q1 -- every day in a 30-day window got ONE fiscal quarter, and
    -- `both_selling_systems_reach_the_pack` fired its "covers only one fiscal
    -- quarter" clause on Snowflake alone. No row count could see it: the
    -- numbers were right and the CALENDAR was wrong.
    --
    -- `floor` is the operation actually wanted and every engine agrees on it.
    -- For non-negative values it is identical to truncation, so this changes
    -- nothing on Fabric or Databricks.
    cast(floor(fiscal_month_index / 3) as int) + 1 as fiscal_quarter,
    fiscal_month_index + 1     as fiscal_period,
    -- The label a report writer actually puts on an axis. Built here so every
    -- surface spells it the same way.
    {{ str_concat("'FY'", "right(cast(fiscal_year as " ~ varchar_n(4) ~ "), 2)") }} as fiscal_year_label,
    {{ str_concat(
        str_concat("'FY'", "right(cast(fiscal_year as " ~ varchar_n(4) ~ "), 2)"),
        str_concat("' Q'", "cast(cast(floor(fiscal_month_index / 3) as int) + 1 as " ~ varchar_n(1) ~ ")")
    ) }} as fiscal_quarter_label
from parts
