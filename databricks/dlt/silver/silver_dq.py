import dlt
from pyspark.sql import functions as F
from functools import reduce 

_DIVERGENCE_THRESHOLD = 0.005  # flag |pct_diff| > 0.5% on close price
_FMP_ENDPOINTS = [
    "profile", "historical_price_full", "historical_price_adjusted",
    "income_statement", "balance_sheet", "cash_flow", "key_metrics",
    "earnings", "dividends", "splits",
]


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
@dlt.table(
    name="coverage_audit",
    comment="(symbol, endpoint) coverage matrix over the bronze.fmp.profile "
            "symbol universe. has_data=false flags an absent combination: "
            "expected for non-payers (AMZN/TSLA dividends, META/PYPL splits) "
            "or a real ingestion gap. Observability per ADR-0020; not a Gold input.",
)
@dlt.expect_or_fail("valid_key", "symbol IS NOT NULL AND endpoint IS NOT NULL")
def coverage_audit():
    symbols = (
        spark.read.table("bronze.fmp.profile")
        .select(F.col("_ticker").alias("symbol")).distinct()
    )
    grid = symbols.crossJoin(
        spark.createDataFrame([(e,) for e in _FMP_ENDPOINTS], ["endpoint"])
    )

    def _counts(endpoint):
        return (
            spark.read.table(f"bronze.fmp.{endpoint}")
            .groupBy(F.col("_ticker").alias("symbol"))
            .agg(F.count(F.lit(1)).alias("record_count"))
            .withColumn("endpoint", F.lit(endpoint))
        )

    actual = reduce(lambda a, b: a.unionByName(b),
                    [_counts(e) for e in _FMP_ENDPOINTS])

    return (
        grid.join(actual, ["symbol", "endpoint"], "left")
        .withColumn("record_count", F.coalesce(F.col("record_count"), F.lit(0)))
        .withColumn("has_data", F.col("record_count") > 0)
    )