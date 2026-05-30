import dlt
from pyspark.sql import functions as F
from pyspark.sql.window import Window


@dlt.table(
    name="daily_prices",
    comment="Cleansed daily OHLCV per (symbol, price_date), deduped to the "
            "latest ingested batch. Source: bronze.fmp.historical_price_full.",
)
@dlt.expect_or_fail("valid_key", "symbol IS NOT NULL AND price_date IS NOT NULL")
@dlt.expect_or_drop("non_negative_price",
                    "open >= 0 AND high >= 0 AND low >= 0 AND close >= 0")
@dlt.expect("rescue_data_clean", "_rescued_data IS NULL")
def daily_prices():
    latest = Window.partitionBy("symbol", "date").orderBy(
        F.col("_batch_date").desc(),
        F.col("_ingest_timestamp").desc(),
    )
    return (
        spark.read.table("bronze.fmp.historical_price_full")
        .withColumn("_rn", F.row_number().over(latest))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
        .withColumn("price_date", F.to_date("date"))
        .select(
            "symbol", "price_date", "open", "high", "low", "close",
            "volume", "vwap", "change", "changePercent",
            "_batch_date", "_source_file", "_rescued_data",
        )
    )
@dlt.table(
    name="daily_prices_adjusted",
    comment="Split/dividend-adjusted daily OHLCV per (symbol, price_date), "
            "deduped to the latest ingested batch. "
            "Source: bronze.fmp.historical_price_adjusted.",
)
@dlt.expect_or_fail("valid_key", "symbol IS NOT NULL AND price_date IS NOT NULL")
@dlt.expect_or_drop("non_negative_price",
                    "adjOpen >= 0 AND adjHigh >= 0 AND adjLow >= 0 AND adjClose >= 0")
@dlt.expect("rescue_data_clean", "_rescued_data IS NULL")
def daily_prices_adjusted():
    latest = Window.partitionBy("symbol", "date").orderBy(
        F.col("_batch_date").desc(),
        F.col("_ingest_timestamp").desc(),
    )
    return (
        spark.read.table("bronze.fmp.historical_price_adjusted")
        .withColumn("_rn", F.row_number().over(latest))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
        .withColumn("price_date", F.to_date("date"))
        .select(
            "symbol", "price_date", "adjOpen", "adjHigh", "adjLow", "adjClose",
            "volume", "_batch_date", "_source_file", "_rescued_data",
        )
    )