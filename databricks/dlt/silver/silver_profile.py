import dlt
from pyspark.sql import functions as F
from pyspark.sql.window import Window

@dlt.table(
    name="profile_latest",
    comment="Latest FMP company profile per symbol, deduped to the most recent "
            "snapshot by _batch_date. Source: bronze.fmp.profile.",
)
@dlt.expect_or_fail("valid_symbol", "symbol IS NOT NULL")
@dlt.expect("rescue_data_clean", "_rescued_data IS NULL")

def profile_latest():
    latest_per_symbol = Window.partitionBy("symbol").orderBy(
        F.col("_batch_date").desc(),
        F.col("_ingest_timestamp").desc(),
    )
    return (
        spark.read.table("bronze.fmp.profile")
        .withColumn("_rn", F.row_number().over(latest_per_symbol))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
    )
VOLATILE_AND_METADATA = [
    "price", "change", "changePercentage", "volume", "averageVolume",
    "marketCap", "beta", "lastDividend", "range",
    "_source", "_endpoint", "_ticker", "_batch_date",
    "_ingest_timestamp", "_source_file", "_loaded_at",
    "_rescued_data",
]


@dlt.view
def profile_source():
    return spark.readStream.table("bronze.fmp.profile")


dlt.create_streaming_table(
    name="company_scd2",
    expect_all_or_fail={"valid_symbol": "symbol IS NOT NULL"},
    expect_all={"rescue_data_clean": "_rescued_data IS NULL"},
)

dlt.create_auto_cdc_flow(
    target="company_scd2",
    source="profile_source",
    keys=["symbol"],
    sequence_by=F.col("_batch_date"),
    stored_as_scd_type=2,
    track_history_except_column_list=VOLATILE_AND_METADATA,
)
