import dlt
from pyspark.sql import functions as F
from pyspark.sql.window import Window

FUNDAMENTALS = [
    "income_statement",
    "balance_sheet",
    "cash_flow",
    "key_metrics",
]


def _make_fundamentals_table(source_table):
    @dlt.table(
        name=source_table,
        comment=f"Cleansed annual {source_table} per (symbol, period_end_date, "
                f"period), deduped to the latest ingested batch. "
                f"Source: bronze.fmp.{source_table}.",
    )
    @dlt.expect_or_fail("valid_key",
                        "symbol IS NOT NULL AND period_end_date IS NOT NULL")
    @dlt.expect("rescue_data_clean", "_rescued_data IS NULL")
    def _fundamentals():
        latest = Window.partitionBy("symbol", "date", "period").orderBy(
            F.col("_batch_date").desc(),
            F.col("_ingest_timestamp").desc(),
        )
        return (
            spark.read.table(f"bronze.fmp.{source_table}")
            .withColumn("_rn", F.row_number().over(latest))
            .filter(F.col("_rn") == 1)
            .drop("_rn")
            .withColumn("period_end_date", F.to_date("date"))
        )
    return _fundamentals


for _name in FUNDAMENTALS:
    _make_fundamentals_table(_name)