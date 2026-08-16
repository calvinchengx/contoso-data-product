"""Bronze: parse landing bytes. No dedupe, no conforming, no quarantine."""

from __future__ import annotations

from typing import Any


def run_bronze(
    spark,
    *,
    landing: str,
    tables: str,
    day: str,
    web_customer_ddl: str,
    web_product_ddl: str,
    web_order_ddl: str,
    web_customer_fields: list[str],
    web_product_fields: list[str],
    web_order_fields: list[str],
) -> dict[str, Any]:
    """Read landing, write bronze Delta tables, return observed metrics.

    `landing` and `tables` are engine paths the consumer resolved
    (OneLake abfs, UC volume, DBFS). This module never names a scheme.
    """
    from pyspark.sql import functions as F

    lineage: list[tuple[str, str]] = []

    def save(df, name: str) -> int:
        df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(
            f"{tables}/{name}"
        )
        lineage.append(("write", f"Tables/{name}"))
        return df.count()

    def landed(path: str) -> str:
        lineage.append(("read", f"Files/landing/{path}"))
        return f"{landing}/{path}"

    def read_json_array(path: str, ddl: str):
        page = F.from_json("value", ddl)
        return spark.read.text(path).select(F.explode(page).alias("r")).select("r.*")

    customers = (
        spark.read.option("header", True)
        .option("inferSchema", False)
        .csv(landed(f"contoso_pos/{day}/customers/"))
    )
    n_cust = save(customers, "bronze_customers")
    orders = spark.read.json(landed(f"contoso_pos/{day}/orders/"))
    n_ord = save(orders, "bronze_orders")

    web_customers = read_json_array(landed(f"contoso_web/{day}/customers/"), web_customer_ddl)
    n_web_cust = save(web_customers, "bronze_web_customers")
    web_products = read_json_array(landed(f"contoso_web/{day}/products/"), web_product_ddl)
    n_web_prod = save(web_products, "bronze_web_products")
    web_orders = read_json_array(landed(f"contoso_web/{day}/orders/"), web_order_ddl)
    n_web_ord = save(web_orders, "bronze_web_orders")

    fx = spark.read.parquet(landed(f"contoso_reference/{day}/fx_rates.parquet"))
    n_fx = save(fx, "bronze_fx_rates")
    hierarchy = spark.read.parquet(landed(f"contoso_reference/{day}/product_hierarchy.parquet"))
    n_hier = save(hierarchy, "bronze_product_hierarchy")
    changes = spark.read.parquet(landed(f"contoso_erp/{day}/changes.parquet"))
    n_erp = save(changes, "bronze_erp_changes")

    distinct_cust = customers.select("customer_id").distinct().count()
    distinct_ord = orders.select("order_id").distinct().count()
    web_emails = {r["email"] for r in web_customers.select("email").distinct().collect()}
    pos_emails = {
        r["email"] for r in customers.select("email").distinct().collect() if r["email"]
    }
    blank = []
    for tname, tdf, tfields in (
        ("bronze_web_customers", web_customers, web_customer_fields),
        ("bronze_web_products", web_products, web_product_fields),
        ("bronze_web_orders", web_orders, web_order_fields),
    ):
        for c in tfields:
            if tdf.filter(F.col(c).isNotNull()).limit(1).count() == 0:
                blank.append(f"{tname}.{c}")

    fx_calendar_span = fx.selectExpr(
        "datediff(max(rate_date), min(rate_date)) + 1 AS days"
    ).collect()[0]["days"]
    try:
        fx_calendar_span = int(fx_calendar_span)
    except (TypeError, ValueError):
        fx_calendar_span = 1

    metrics = {
        "bronze_customers": n_cust,
        "distinct_customers": distinct_cust,
        "customer_columns": len(customers.columns),
        "customer_column_names": ",".join(customers.columns),
        "bronze_orders": n_ord,
        "distinct_orders": distinct_ord,
        "bronze_web_customers": n_web_cust,
        "bronze_web_products": n_web_prod,
        "bronze_web_orders": n_web_ord,
        "web_orders_has_lines": "lines" in web_orders.columns,
        "blank_columns": ",".join(sorted(blank)),
        "shared_emails": len(web_emails & pos_emails),
        "bronze_fx_rates": n_fx,
        "fx_currencies": fx.select("currency").distinct().count(),
        "fx_published_days": fx.select("rate_date").distinct().count(),
        "fx_calendar_span": fx_calendar_span,
        "bronze_product_hierarchy": n_hier,
        "departments": hierarchy.select("department").distinct().count(),
        "bronze_erp_changes": n_erp,
        "lineage": lineage,
    }

    spark.createDataFrame(
        [
            (
                metrics["bronze_customers"],
                metrics["distinct_customers"],
                metrics["customer_columns"],
                metrics["customer_column_names"],
                metrics["bronze_orders"],
                metrics["distinct_orders"],
                metrics["bronze_web_customers"],
                metrics["bronze_web_products"],
                metrics["bronze_web_orders"],
                metrics["web_orders_has_lines"],
                metrics["blank_columns"],
                metrics["shared_emails"],
                metrics["bronze_fx_rates"],
                metrics["fx_currencies"],
                metrics["fx_published_days"],
                metrics["fx_calendar_span"],
                metrics["bronze_product_hierarchy"],
                metrics["departments"],
                metrics["bronze_erp_changes"],
            )
        ],
        "bronze_customers long, distinct_customers long, customer_columns long, "
        "customer_column_names string, "
        "bronze_orders long, distinct_orders long, "
        "bronze_web_customers long, bronze_web_products long, bronze_web_orders long, "
        "web_orders_has_lines boolean, blank_columns string, shared_emails long, "
        "bronze_fx_rates long, fx_currencies long, fx_published_days long, "
        "fx_calendar_span long, "
        "bronze_product_hierarchy long, departments long, bronze_erp_changes long",
    ).write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(
        f"{tables}/bronze_ingest_metrics"
    )
    return metrics
