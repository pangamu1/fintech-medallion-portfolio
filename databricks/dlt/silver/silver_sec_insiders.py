import dlt
from pyspark.sql import functions as F
from pyspark.sql.window import Window

_SOURCE = "bronze.sec.insider_transactions"

# Form 4 dates land as ISO strings; type them so Gold's pit-join works.
_DATE_COLS = ["transaction_date", "exercise_date", "expiration_date", "period_of_report"]
# Numeric leaves arrive as strings (some legitimately NULL — RSU price, derivative-only).
_NUMERIC_COLS = [
    "transaction_shares",
    "transaction_price_per_share",
    "shares_owned_following",
    "conversion_or_exercise_price",
    "underlying_security_shares",
]


@dlt.table(
    name="insider_transactions",
    comment="Forward-only Silver event table from bronze.sec.insider_transactions "
            "(Form 4 lines), scoped to trades in our own securities "
            "(ticker = issuer_symbol; drops outbound 10%-owner stakes like "
            "Alphabet→LIFE), deduped per (accession, table, line_index). "
            "Dates + numerics typed; no SCD2.",
)
@dlt.expect_or_fail(
    "valid_key",
    "accession IS NOT NULL AND `table` IS NOT NULL "
    "AND line_index IS NOT NULL AND transaction_date IS NOT NULL",
)
@dlt.expect("rescue_data_clean", "_rescued_data IS NULL")
@dlt.expect("shares_non_negative", "transaction_shares >= 0")
@dlt.expect("symbol_matches", "ticker = issuer_symbol")

def insider_transactions():
    latest = Window.partitionBy("accession", "table", "line_index").orderBy(
        F.col("_batch_date").desc(),
        F.col("_ingest_timestamp").desc(),
    )
    df = (
        spark.read.table(_SOURCE)
        .filter(F.col("ticker") == F.col("issuer_symbol"))
        .withColumn("_rn", F.row_number().over(latest))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
    )
    for col in _DATE_COLS:
        df = df.withColumn(col, F.to_date(col))
    for col in _NUMERIC_COLS:
        df = df.withColumn(col, F.col(col).cast("double"))
    return df
