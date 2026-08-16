"""Silver: conform, resolve identity, carry FX forward. Gold reads only silver."""

from __future__ import annotations

from typing import Any

MONEY = "decimal(19,4)"
RATE = "decimal(19,6)"

COUNTRY = {
    "US": "US",
    "USA": "US",
    "U.S.": "US",
    "UNITED STATES": "US",
    "GB": "GB",
    "GBR": "GB",
    "UK": "GB",
    "U.K.": "GB",
    "UNITED KINGDOM": "GB",
    "SG": "SG",
    "SGP": "SG",
    "SINGAPORE": "SG",
}


def run_silver(spark, *, tables: str) -> dict[str, Any]:
    """Read bronze Delta, write silver Delta, return observed metrics."""
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    lineage: list[tuple[str, str]] = []

    def read(name: str):
        lineage.append(("read", f"Tables/{name}"))
        return spark.read.format("delta").load(f"{tables}/{name}")

    def save(df, name: str) -> int:
        df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(
            f"{tables}/{name}"
        )
        lineage.append(("write", f"Tables/{name}"))
        return df.count()

    conform = F.create_map([F.lit(x) for kv in COUNTRY.items() for x in kv])
    country_key = F.upper(F.trim(F.col("country")))

    c = read("bronze_customers")
    customers = (
        c.withColumn(
            "_rn",
            F.row_number().over(Window.partitionBy("customer_id").orderBy("customer_id")),
        )
        .filter(F.col("_rn") == 1)
        .drop("_rn")
        .withColumn("email", F.lower(F.trim(F.coalesce(F.col("email"), F.lit("")))))
        .withColumn("country", F.coalesce(conform[country_key], country_key))
    )
    n_cust = save(customers, "silver_customers")

    latest = Window.partitionBy("order_id").orderBy(F.col("event_seq").desc())
    o = read("bronze_orders").withColumn("_rn", F.row_number().over(latest)).filter(F.col("_rn") == 1).drop("_rn")
    bad = (F.col("quantity") <= 0) | F.col("unit_price").isNull()
    clean = (
        o.filter(~bad)
        .withColumn("unit_price", F.col("unit_price").cast(MONEY))
        .withColumn("amount", (F.col("quantity") * F.col("unit_price")).cast(MONEY))
    )
    n_ord = save(clean, "silver_orders")
    n_quar = save(o.filter(bad), "silver_quarantine_orders")

    hierarchy = read("bronze_product_hierarchy").withColumn(
        "list_price_usd", F.col("list_price_usd").cast(MONEY)
    )
    n_hier = save(hierarchy, "silver_product_hierarchy")

    fx = read("bronze_fx_rates").withColumn("rate_date", F.to_date("rate_date"))
    bounds = fx.selectExpr("min(rate_date) AS lo", "max(rate_date) AS hi").collect()[0]
    n_days = (bounds["hi"] - bounds["lo"]).days + 1
    calendar = spark.range(n_days).select(
        F.date_add(F.lit(bounds["lo"]), F.col("id").cast("int")).alias("rate_date")
    )
    currencies = fx.select("currency").distinct()
    dense = calendar.crossJoin(currencies)
    effective = (
        dense.alias("d")
        .join(
            fx.alias("p"),
            (F.col("d.currency") == F.col("p.currency"))
            & (F.col("p.rate_date") <= F.col("d.rate_date")),
        )
        .groupBy("d.rate_date", "d.currency")
        .agg(F.max("p.rate_date").alias("_quoted_on"))
    )
    fx_daily = (
        effective.alias("e")
        .join(
            fx.alias("q"),
            (F.col("e.currency") == F.col("q.currency"))
            & (F.col("e._quoted_on") == F.col("q.rate_date")),
        )
        .select(
            F.col("e.rate_date").alias("rate_date"),
            F.col("e.currency").alias("currency"),
            F.col("q.rate_to_usd").cast(RATE).alias("rate_to_usd"),
            F.col("e._quoted_on").alias("quoted_on"),
            (F.col("e._quoted_on") != F.col("e.rate_date")).alias("rate_is_carried"),
        )
    )
    n_fx = save(fx_daily, "silver_fx_daily")

    spark.conf.set("spark.sql.session.timeZone", "UTC")
    web_customers = (
        read("bronze_web_customers")
        .withColumn("email", F.lower(F.trim(F.col("email"))))
        .withColumn(
            "country",
            F.coalesce(
                conform[F.upper(F.trim(F.col("country")))],
                F.upper(F.trim(F.col("country"))),
            ),
        )
    )
    n_web_cust = save(web_customers, "silver_web_customers")

    web_lines = (
        read("bronze_web_orders")
        .withColumn("line", F.explode("lines"))
        .withColumn("email", F.lower(F.trim(F.col("email"))))
        .withColumn("placed_utc", F.to_timestamp("placed_at"))
        .withColumn("order_date", F.date_format(F.to_date(F.col("placed_utc")), "yyyy-MM-dd"))
        .select(
            F.col("web_order_id"),
            F.col("email"),
            F.col("order_date"),
            F.col("status"),
            F.col("line.line_no").cast("int").alias("line_no"),
            F.col("line.product_id").alias("product_id"),
            F.col("line.quantity").cast("int").alias("quantity"),
            F.col("line.unit_price").cast(MONEY).alias("unit_price"),
            (F.col("line.quantity").cast("int") * F.col("line.unit_price").cast(MONEY))
            .cast(MONEY)
            .alias("amount"),
            F.lit("USD").alias("currency"),
        )
    )
    n_web_lines = save(web_lines, "silver_web_order_lines")
    web_span = web_lines.selectExpr("min(order_date) AS lo", "max(order_date) AS hi").collect()[0]

    pos = read("silver_customers").select(
        "customer_id", "email", "country", "marketing_segment", "loyalty_tier"
    )
    pos_keyed = pos.withColumn(
        "party_key",
        F.when(F.col("email") == "", F.concat(F.lit("pos:"), F.col("customer_id"))).otherwise(
            F.concat(F.lit("email:"), F.col("email"))
        ),
    )
    web_keyed = web_customers.select("email", "country").withColumn(
        "party_key", F.concat(F.lit("email:"), F.col("email"))
    )
    party = (
        pos_keyed.alias("p")
        .join(web_keyed.alias("w"), on="party_key", how="full_outer")
        .select(
            F.col("party_key"),
            F.coalesce(F.col("p.email"), F.col("w.email")).alias("email"),
            F.col("p.customer_id").alias("pos_customer_id"),
            F.col("p.customer_id").isNotNull().alias("in_pos"),
            F.col("w.email").isNotNull().alias("in_web"),
            F.coalesce(F.col("p.country"), F.col("w.country")).alias("country"),
            F.col("p.marketing_segment").alias("marketing_segment"),
            F.col("p.loyalty_tier").alias("loyalty_tier"),
        )
    )
    n_party = save(party, "silver_party")

    naive = (
        read("bronze_customers")
        .select("email")
        .filter(F.col("email").isNotNull() & (F.col("email") != ""))
        .distinct()
        .join(read("bronze_web_customers").select("email").distinct(), on="email")
        .count()
    )

    return {
        "silver_customers": n_cust,
        "silver_orders": n_ord,
        "silver_quarantine_orders": n_quar,
        "customer_columns": len(customers.columns),
        "countries": sorted({r["country"] for r in customers.select("country").distinct().collect()}),
        "missing_email": customers.filter(F.col("email") == "").count(),
        "silver_product_hierarchy": n_hier,
        "silver_fx_daily": n_fx,
        "fx_carried": fx_daily.filter(F.col("rate_is_carried")).count(),
        "fx_currencies": currencies.count(),
        "fx_calendar_days": n_days,
        "silver_web_customers": n_web_cust,
        "silver_web_order_lines": n_web_lines,
        "silver_party": n_party,
        "party_matched": party.filter(F.col("in_pos") & F.col("in_web")).count(),
        "party_pos_only": party.filter(F.col("in_pos") & ~F.col("in_web")).count(),
        "party_web_only": party.filter(~F.col("in_pos") & F.col("in_web")).count(),
        "party_no_email": party.filter(F.col("email") == "").count(),
        "naive_case_sensitive_matches": naive,
        "web_order_date_span": [web_span["lo"], web_span["hi"]],
        "lineage": lineage,
    }
