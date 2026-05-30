import dlt
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# Forward-only event tables (earnings + corporate actions). Identical handling:
# dedup to the latest batch per (symbol, date), add a typed event_date, keep all
# columns (tiny tables) for Gold to project. NO non-negative drop — epsActual is
# legitimately negative on loss quarters (same lesson as the fundamentals).
_EVENT_TABLES = ["earnings", "dividends", "splits"]


def _make_event_table(source_table):
    @dlt.table(
        name=source_table,
        comment=f"Forward-only Silver event table from bronze.fmp.{source_table}, "
                f"deduped to the latest ingested batch per (symbol, date). "
                f"event_date = typed DATE of the source `date` string.",
    )
    @dlt.expect_or_fail("valid_key", "symbol IS NOT NULL AND event_date IS NOT NULL")
    @dlt.expect("rescue_data_clean", "_rescued_data IS NULL")
    def _event_table():
        latest = Window.partitionBy("symbol", "date").orderBy(
            F.col("_batch_date").desc(),
            F.col("_ingest_timestamp").desc(),
        )
        return (
            spark.read.table(f"bronze.fmp.{source_table}")
            .withColumn("_rn", F.row_number().over(latest))
            .filter(F.col("_rn") == 1)
            .drop("_rn")
            .withColumn("event_date", F.to_date("date"))
        )
    return _event_table


for _t in _EVENT_TABLES:
    _make_event_table(_t)