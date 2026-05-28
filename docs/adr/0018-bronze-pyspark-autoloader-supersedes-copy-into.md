# 0018 — Bronze runs on PySpark Autoloader; supersedes `COPY INTO` for the Bronze layer

- **Status:** Accepted; cardinality row amended by [ADR-0019](0019-alpha-vantage-deferred-from-bronze.md) on 2026-05-27 (Alpha Vantage deferred from Bronze → 10 streams, FMP only).
- **Date:** 2026-05-26
- **Deciders:** project owner
- **Supersedes:** the Bronze row of [ADR-0002](0002-medallion-layer-ownership.md). ADR-0002's Silver (DLT) and Gold (dbt) ownership rows are untouched.

## Context

[ADR-0002](0002-medallion-layer-ownership.md) assigned Bronze to Databricks via `COPY INTO` + Delta. Working through the `feat/bronze-databricks` plan exposed two pressures that motivated revisiting that choice mid-branch:

1. **Stack-wide language balance.** Gold is SQL (dbt models). Bronze on `COPY INTO` would also be SQL. The only PySpark surface in the project would then be Silver/DLT — a thin slice that under-represents the Spark API for an end-to-end Data Engineering portfolio.
2. **Autoloader is the modern Databricks Bronze pattern.** `cloudFiles` with `.trigger(availableNow=True)` has effectively replaced `COPY INTO` at most production shops over the past few years. It scales to streaming with no code change, supports schema-evolution modes that `COPY INTO` does not (`rescue`, `addNewColumns`), and lets us run arbitrary PySpark transformations between read and write.

A pre-pivot probe on 2026-05-26 (notebook `probe_serverless` in Databricks Free Edition) established that:

- Free Edition exposes **serverless general-purpose compute** for notebooks (in addition to Serverless SQL Warehouse and serverless DLT). Runtime is Spark Connect, Spark 4.1.0.
- `spark.read.json` against `/Volumes/ingestion/fmp/raw_jsons/profile/` parses correctly **only with `multiLine = "true"`**. Without the option every row collapses into `_corrupt_record`, because `save_to_lake()` in [`fintech_datalake/scripts/utils.py`](../../fintech_datalake/scripts/utils.py) writes pretty-printed JSON, not NDJSON.
- The local-Bronze file shape produced by `save_to_lake()` is `{ _ingest_timestamp, _source, _endpoint, _ticker, _batch_date, data: [...] }` — a 5-column envelope wrapping a `data` array of the actual API records.

This ADR is **not** motivated by Autoloader being strictly better at idempotency than `COPY INTO`. Both work. `COPY INTO` tracks processed files in the Delta table's transaction log (tracking coupled to the table). Autoloader tracks them in a checkpoint directory (RocksDB-backed, decoupled from the table). The decoupled model is more flexible and more fragile; we accept that trade-off in exchange for everything else Autoloader provides.

## Decision

The Bronze layer is implemented in **PySpark using Databricks Autoloader (`cloudFiles`) in batch-trigger mode**, not `COPY INTO`.

| Concern | Choice |
|---|---|
| Read engine | `spark.readStream.format("cloudFiles")` |
| Trigger | `.trigger(availableNow=True)` — batch-shaped: process all available files across as many micro-batches as needed, then stop. (`trigger(once=True)` is deprecated; do not use it.) |
| Schema evolution mode | `cloudFiles.schemaEvolutionMode = "rescue"` — schema is locked at first inference; unexpected fields land in a `_rescued_data` JSON-string column |
| Column type inference | `cloudFiles.inferColumnTypes = "true"` — Autoloader defaults this to **false** (all columns inferred as `string`), opposite of batch `spark.read.json` defaults. Must be enabled explicitly for `data` to parse as `array<struct<…>>` rather than a JSON-encoded string |
| JSON parse option | `multiLine = "true"` — mandatory; producer writes one JSON document per file, not NDJSON |
| Stream cardinality | One stream per `(source, endpoint)` — originally 11 streams (1 Alpha Vantage + 10 FMP). **Amended by [ADR-0019](0019-alpha-vantage-deferred-from-bronze.md) on 2026-05-27 to 10 streams (FMP only)**; Alpha Vantage's `TIME_SERIES_DAILY` payload shape (date-keyed struct, not array) does not fit the `explode(data)` pattern and is consumed at Silver instead |
| Row granularity | `explode(col("data"))` between read and write — one Bronze row per actual API record; envelope columns flattened onto each row; raw `data` array column dropped (**Path B**) |
| Sink | Delta table `bronze.<source>.<endpoint>`, append mode |
| Checkpoint location | `/Volumes/ingestion/<source>/raw_jsons/_checkpoints/<endpoint>/` — nested *inside* the existing `raw_jsons` volume. UC's path grammar requires `/Volumes/<cat>/<sch>/<volume>/…` where `<volume>` must be a registered volume; a sibling-to-volume `_checkpoints` dir is rejected as `UC_VOLUME_NOT_FOUND`. Leading `_` still distinguishes ops state from raw inputs. See Amendments §2026-05-27 |
| Compute | Serverless general-purpose (Spark Connect runtime) |
| Code location | `.py` files in repo under `databricks/jobs/bronze_autoloader/` |
| Workspace sync | Terraform `databricks_workspace_file` resource |
| Job definition | Terraform `databricks_job` with `spark_python_task` pointing at the synced workspace file; one job per `(source, endpoint)` via `for_each` |

ADR-0002's Silver (DLT) and Gold (dbt) ownership decisions are unchanged. ADR-0002's Bronze row is partially superseded; an in-place status amendment on ADR-0002 carries a forward pointer to this ADR per MADR convention.

## Considered alternatives

- **Stay on `COPY INTO`** (ADR-0002 status quo) — rejected for portfolio language balance and because Autoloader is the more interview-relevant modern pattern. Idempotency-wise the two are roughly equivalent.
- **Vanilla batch `spark.read.json().write.mode("append").saveAsTable(...)`** — rejected. Hand-rolling idempotency (anti-join on `_metadata.file_name` or a manifest table) reproduces what Autoloader provides for free, and the result reads like a Spark-101 exercise rather than a production pattern.
- **Full streaming Autoloader (`.trigger(processingTime=...)`)** — rejected. The source is a once-daily local Python job; continuous streaming buys nothing and wastes compute.
- **One stream per source (2 streams) instead of per endpoint (11)** — rejected. Profile rows and income-statement rows have entirely different schemas; a single stream over both would either infer a near-empty union schema with everything in `_rescued_data`, or require `foreachBatch` with manual per-row routing to 11 destination tables. Either path throws away every simplicity argument for the pivot.
- **Run Bronze through DLT** (re-using the Silver runner) — rejected. Would blur ADR-0002's layer-ownership table by making DLT the engine for both Bronze and Silver, and DLT's pipeline model is heavier than needed for a deterministic file-landing zone. We keep DLT scoped to Silver where its expectations and auto-CDC actually earn the complexity.
- **Hybrid: `COPY INTO` for some endpoints, Autoloader for others** — rejected. Demonstrating two patterns doubles maintenance for a portfolio repo with only 11 endpoints. One pattern done well beats two done shallowly.
- **Path A row granularity (keep `data` as a nested-array column on a one-row-per-file Bronze)** — rejected. The envelope is *our* metadata, not source data; the actual API record is `data[i]`. Forcing every downstream consumer (Silver/Gold) to `explode` a nested array is real friction, especially on Spark Connect where some array-handling UDFs are unavailable. Strict interpretation of "Bronze does no transformation" is preserved by treating `explode` as structural de-enveloping rather than business logic.
- **Path C row granularity (dual write: `bronze_raw.*` for Path A plus `bronze.*` for Path B)** — rejected. 2× Delta tables, 2× checkpoints, 2× jobs for marginal lineage benefit at this project's scale.

## Consequences

- **Positive:**
  - Stack now has meaningful PySpark surface area in Bronze and Silver, balanced against SQL in Gold. Stronger end-to-end DE portfolio narrative.
  - Autoloader's checkpoint isolates file-tracking state from the table — we can rebuild the Bronze table without losing tracking, or rebuild the checkpoint without affecting the table.
  - Rescue-mode schema evolution preserves *everything*: typed columns stay stable; new fields captured in `_rescued_data`. Bronze becomes a true superset of producer output without forcing stream restarts.
  - Per-endpoint streams give clean failure isolation: one bad file in `dividends` does not block `profile`.
- **Negative / cost:**
  - 11 streams × 11 checkpoints = 11 ops artifacts to monitor. `COPY INTO`'s single-table tracking model would have given one less artifact per pipeline.
  - **Loss-of-checkpoint failure mode:** deleting the checkpoint dir causes re-processing of all files → duplicate rows in Bronze (append-only Delta does not dedupe). Mitigation: operational runbook — `TRUNCATE TABLE bronze.<source>.<endpoint>` + delete checkpoint dir + re-run. No automation at current scale.
  - **0-event files** (e.g., `dividends` for a no-dividend ticker) produce zero Bronze rows. The file is processed and tracked in the checkpoint but invisible in Bronze. Detection deferred to a future side audit table (`bronze.<source>._file_audit`), built via `.foreachBatch`.
  - **File-rewrite semantics:** Autoloader by default does **not** re-process modified files (`cloudFiles.allowOverwrites = false`). Our daily upload writes new filenames (`<ticker>_<batch_date>.json`) so this is fine for the happy path. If a corrected file is ever re-uploaded with the same path, Autoloader will skip it. Flag for CP10 verification.
  - **Spark Connect (the serverless runtime)** lacks a small slice of PySpark APIs (RDD-level ops, `sparkContext` internals). Autoloader's surface is fully supported; this matters only if future Bronze logic ever needs RDD-level operations.
  - "I have shipped `COPY INTO` for Bronze" is no longer a true claim. Trade-off accepted for the Autoloader narrative.
  - **Compute model is now mixed:** SQL Warehouse for ad-hoc and dbt-targeted queries, serverless general-purpose for the Bronze Autoloader jobs, serverless DLT for Silver. Three compute surfaces, three sets of cold-start characteristics to monitor.
- **Follow-ups required:**
  - Plan file `~/.claude/plans/feat-bronze-databricks.md` — CP7–CP10 rewritten from `COPY INTO` SQL to Autoloader PySpark (done in same session as this ADR).
  - In-place status amendment on [ADR-0002](0002-medallion-layer-ownership.md) noting the partial Bronze supersession (done in same session).
  - `CLAUDE.md` Layer-ownership table — engine column changed from "`COPY INTO` + Delta" to "PySpark Autoloader + Delta" (done in same session).
  - Stretch CP (this branch or future): `bronze.<source>._file_audit` side table via `.foreachBatch` to mitigate 0-event-file invisibility.

## Amendments

### 2026-05-27 — CP7 probe corrections

The CP7 Autoloader probe surfaced three implementation details that diverged from this ADR's initial draft. The Decision table above has been updated in place; this section records what was wrong and why, for traceability.

1. **Checkpoint path scheme corrected.** Original draft specified `/Volumes/ingestion/<source>/_checkpoints/<endpoint>/`. This is rejected by UC with `[UC_VOLUME_NOT_FOUND] Volume 'ingestion.<source>._checkpoints' does not exist.` UC volume paths require `/Volumes/<catalog>/<schema>/<volume>/…` where `<volume>` is a registered volume; `_checkpoints` was being treated as a (non-existent) sibling volume to `raw_jsons`. Resolution: nest the checkpoint under the existing `raw_jsons` volume → `/Volumes/ingestion/<source>/raw_jsons/_checkpoints/<endpoint>/`. The leading-underscore convention still hides it from Autoloader's directory discovery. Trade-off: ops state colocated with source data in one volume rather than separated. Acceptable; promotable to a dedicated `databricks_volume.checkpoints` per source in a future branch if cleaner separation becomes worth the TF churn.

2. **`cloudFiles.inferColumnTypes` must be explicitly enabled.** This option was missing from the original Decision table. Autoloader's default (`false`) infers every column as `string` — the opposite of batch `spark.read.json` (default `true`). With the default, the `data` array column came back as a JSON-encoded string, breaking the `explode(col("data"))` step. Resolution: set `cloudFiles.inferColumnTypes = "true"` explicitly. The combination with `schemaEvolutionMode = "rescue"` is intentional: rich types at first inference, then frozen — drift goes to `_rescued_data`.

3. **No explicit `CREATE TABLE` DDL.** The `feat/bronze-databricks` plan file's CP1 locked "explicit `CREATE TABLE` per Bronze table." The actual implementation uses `.toTable(table)` on the write stream, which atomically creates the table from the streaming DataFrame's schema on first write. Explicit DDL would risk drift between hand-written column lists and Autoloader's inferred schema; rescue mode already handles evolution at the `_rescued_data` level rather than at the table-schema level. The CP1 decision is treated as reversed by this ADR's implementation.

## References

- [ADR-0002](0002-medallion-layer-ownership.md) — original Bronze ownership; partially superseded by this ADR.
- [ADR-0007](0007-bronze-ingestion-durability-atomic-writes-jsonl-logs.md) — local-Bronze envelope and durability guarantees; producer-side schema this ADR consumes.
- [ADR-0014](0014-terraform-for-iac.md) — Terraform-for-IaC scope; the `databricks_job` + `databricks_workspace_file` resources this ADR introduces fall under it.
- [ADR-0016](0016-free-edition-default-storage-workaround.md) — Free Edition Default Storage context; the UC volumes Autoloader reads from were created under this constraint.
- Databricks Autoloader docs — https://docs.databricks.com/ingestion/auto-loader/index.html
- Autoloader schema-evolution modes — https://docs.databricks.com/ingestion/auto-loader/schema.html
- `trigger(availableNow=True)` semantics — https://docs.databricks.com/structured-streaming/triggers.html
- Plan file `~/.claude/plans/feat-bronze-databricks.md` — CP-PROBE session that motivated this ADR; CP7+ rewrite that implements it.
