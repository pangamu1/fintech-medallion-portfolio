import dlt
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import StructType, StructField, StringType, MapType

# Type the inner series as a MAP so Spark doesn't infer one struct field per
# calendar date (which would explode the schema across files / batches).
_OHLCV = StructType([
    StructField("1. open",   StringType()),
    StructField("2. high",   StringType()),
    StructField("3. low",    StringType()),
    StructField("4. close",  StringType()),
    StructField("5. volume", StringType()),
])

_AV_SCHEMA = StructType([
    StructField("_ingest_timestamp", StringType()),
    StructField("_ticker",           StringType()),
    StructField("_batch_date",       StringType()),
    StructField("data", StructType([
        StructField("Time Series (Daily)", MapType(StringType(), _OHLCV)),
    ])),
])

_AV_PATH = "/Volumes/ingestion/alpha_vantage/raw_jsons/time_series_daily/"


@dlt.table(
    name="daily_prices",
    comment="Alpha Vantage daily OHLCV per (symbol, price_date), pivoted from the "
            "date-keyed time-series map, deduped to the latest batch. "
            "Source: ingestion.alpha_vantage.raw_jsons (ADR-0019).",
)
@dlt.expect_or_fail("valid_key", "symbol IS NOT NULL AND price_date IS NOT NULL")
@dlt.expect_or_drop("non_negative_price",
                    "open >= 0 AND high >= 0 AND low >= 0 AND close >= 0")
def daily_prices():
    exploded = (
        spark.read.schema(_AV_SCHEMA).option("multiLine", "true").json(_AV_PATH)
        .select(
            F.col("_ticker").alias("symbol"),
            "_batch_date", "_ingest_timestamp",
            F.explode(F.col("data.`Time Series (Daily)`")).alias("date_str", "ohlcv"),
        )
    )
    latest = Window.partitionBy("symbol", "date_str").orderBy(
        F.col("_batch_date").desc(), F.col("_ingest_timestamp").desc(),
    )
    return (
        exploded.withColumn("_rn", F.row_number().over(latest))
        .filter(F.col("_rn") == 1).drop("_rn")
        .select(
            "symbol",
            F.to_date("date_str").alias("price_date"),
            F.col("ohlcv.`1. open`").cast("double").alias("open"),
            F.col("ohlcv.`2. high`").cast("double").alias("high"),
            F.col("ohlcv.`3. low`").cast("double").alias("low"),
            F.col("ohlcv.`4. close`").cast("double").alias("close"),
            F.col("ohlcv.`5. volume`").cast("long").alias("volume"),
            "_batch_date",
        )
    )