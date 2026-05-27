"""
Bronze Autoloader job — promotes local Bronze JSONs in UC volumes into Delta tables.

Run as a Databricks Job on serverless compute. One job per (source, endpoint) pair.
See ADR-0018 for the architectural rationale.
"""

from __future__ import annotations

import argparse


def main(source: str, endpoint: str) -> None:
    """Run the Autoloader stream for one (source, endpoint) pair."""
    from pyspark.sql import SparkSession
    from pyspark.sql.functions import col, current_timestamp, explode

    spark = SparkSession.builder.getOrCreate()

    data_path = f"/Volumes/ingestion/{source}/raw_jsons/{endpoint}/"
    ckpt_path = f"/Volumes/ingestion/{source}/raw_jsons/_checkpoints/{endpoint}/"
    table     = f"bronze.{source}.{endpoint}"

    df = (spark.readStream
          .format("cloudFiles")
          .option("cloudFiles.format", "json")
          .option("cloudFiles.schemaLocation", ckpt_path)
          .option("cloudFiles.inferColumnTypes", "true")
          .option("cloudFiles.schemaEvolutionMode", "rescue")
          .option("multiLine", "true")
          .load(data_path))

    bronze = (df
              .withColumn("_source_file", col("_metadata.file_path"))
              .withColumn("_loaded_at",   current_timestamp())
              .withColumn("record",       explode(col("data")))
              .drop("data")
              .select("_source", "_endpoint", "_ticker", "_batch_date",
                      "_ingest_timestamp", "_source_file", "_loaded_at",
                      "record.*", "_rescued_data"))

    (bronze.writeStream
           .format("delta")
           .outputMode("append")
           .option("checkpointLocation", ckpt_path)
           .trigger(availableNow=True)
           .toTable(table)
           .awaitTermination())

    print(f"[bronze_autoloader] {table} stream complete.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",   required=True, help="e.g. fmp, alpha_vantage")
    parser.add_argument("--endpoint", required=True, help="e.g. profile, historical-price-eod-full")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    main(args.source, args.endpoint)