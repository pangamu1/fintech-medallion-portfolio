# 0007 — Bronze ingestion durability: atomic writes and JSONL audit logs

- **Status:** Accepted
- **Date:** 2026-05-22
- **Deciders:** project owner

## Context

The local Python ingestion phase (`feat/ingest-scaffold`) writes two kinds of files repeatedly during a refresh: (1) Bronze JSON blobs under `fintech_datalake/bronze/{source}/{endpoint}/` — one per (ticker, endpoint) per day; (2) an audit log of every API call attempted, regardless of success.

Both have failure-mode requirements that aren't satisfied by the obvious naive implementations:

**Bronze writes.** A crash, kill signal, or full disk during `open(path, 'w'); f.write(json.dumps(...))` can leave a half-written or zero-byte JSON file at the final path. The next ingestion pass — or worse, the downstream `COPY INTO` into Databricks Bronze — will then read a corrupt file and either crash or silently ingest garbage. The handoff doc's reference code uses a plain `open(...).write(...)` and has this bug.

**Audit log.** The naive shape is a single JSON file containing an array of run records, rewritten on every append. That's O(n²) over the project lifetime, races on concurrent writers, and corrupts on mid-write crash. The handoff doc uses this shape too.

We need both write paths to be crash-safe and append-friendly.

## Decision

**Bronze writes are atomic.** `utils.save_to_lake()` writes the JSON payload to a sibling `.tmp` path in the same directory, then `os.rename()` (or `Path.rename()`) it onto the final path. Same-directory rename is atomic on POSIX filesystems; a crash mid-write leaves only the `.tmp` file, never a half-written final file. The downstream reader sees either the complete previous version or the complete new version, never an intermediate state.

**Audit log is JSON Lines (`.jsonl`).** `utils.log_run()` opens `fintech_datalake/logs/ingestion_log.jsonl` in append mode (`'a'`) and writes one JSON object per line, followed by `\n`. Each line is independently parseable. Appending is O(1) — POSIX guarantees `write()` calls under `PIPE_BUF` (4096 bytes) are atomic, and our log records are well under that. The file is `tail -f`-able during a run, `jq`-readable after, and pandas can read it with `pd.read_json(..., lines=True)`.

## Considered alternatives

- **Plain `open(path, 'w')` for Bronze** — rejected. The crash-corruption window is short but real; a single bad ingest can pollute Bronze and propagate downstream. The atomic-rename pattern costs one extra line of code per write.
- **`fsync` after write, no atomic rename** — rejected. `fsync` flushes buffers but doesn't make the *rename* atomic; you can still have a half-written file at the final path if the process dies between `write()` and `close()`. Atomic rename solves the actual problem.
- **JSON array log rewritten on every append** — rejected. O(n²) IO, races on concurrent writers, corrupts on mid-write crash, no streaming consumption.
- **SQLite for the audit log** — rejected. Adds a dependency for a use case that JSONL handles natively. Trades a one-line `open('a')` for a connection + cursor + commit; not worth it at this scale.
- **`logging` module → file handler for the audit log** — rejected for the structured audit record (we still use `logging` for human-readable runtime output). Structured records are easier to query as JSONL than as parsed log lines.

## Consequences

- **Positive:** Crashes during ingestion can't corrupt Bronze or the audit log. `tail -f` on the JSONL log gives a live progress view. The audit log is directly loadable into pandas / DuckDB / `jq` for post-run analysis without parsing tricks.
- **Negative / cost:** Two patterns the user has to remember and apply consistently. Reviewers unfamiliar with JSONL may not realize each line is independent. The `.tmp` sibling file briefly appears next to the target during writes (cosmetic, but worth knowing if a reviewer watches the directory).
- **Follow-ups required:** When Silver / Gold ingestion code is written, it should read the JSONL log via `pd.read_json(..., lines=True)` or DuckDB's `read_json_auto(filename='*.jsonl')`, never assume a JSON array. Document this in `feat/silver-dlt`.

## References

- Atomic rename guarantees on POSIX — https://man7.org/linux/man-pages/man2/rename.2.html
- JSON Lines spec — https://jsonlines.org/
- `utils.save_to_lake` and `utils.log_run` in `fintech_datalake/scripts/utils.py`
- Handoff doc §6 (the anti-pattern reference shape) — `.claude/notes/fintech_pipeline_handoff.md`
