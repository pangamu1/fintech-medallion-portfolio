import dlt
from pyspark.sql import functions as F

_DIVERGENCE_THRESHOLD = 0.005  # flag |pct_diff| > 0.5% on close price


@dlt.table(
    name="price_cross_validation",
    comment="FMP vs Alpha Vantage daily close reconciliation per "
            "(symbol, price_date). Audit-only per ADR-0009; not a Gold input. "
            "is_divergent flags pct_diff > 0.5%.",
)
@dlt.expect_or_fail("valid_key", "symbol IS NOT NULL AND price_date IS NOT NULL")
def price_cross_validation():
    fmp = (
        spark.read.table("silver.fmp.daily_prices")
        .select("symbol", "price_date", F.col("close").alias("fmp_close"))
    )
    av = (
        spark.read.table("silver.alpha_vantage.daily_prices")
        .select("symbol", "price_date", F.col("close").alias("av_close"))
    )
    return (
        fmp.join(av, ["symbol", "price_date"], "inner")
        .withColumn("abs_diff", F.abs(F.col("fmp_close") - F.col("av_close")))
        .withColumn(
            "pct_diff",
            F.when(F.col("fmp_close") != 0,
                   F.col("abs_diff") / F.col("fmp_close")),
        )
        .withColumn("is_divergent",
                    F.col("pct_diff") > F.lit(_DIVERGENCE_THRESHOLD))
    )