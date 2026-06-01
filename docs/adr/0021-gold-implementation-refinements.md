# 0021 — Gold star-schema implementation refinements to ADR-0013

- **Status:** Accepted
- **Date:** 2026-06-01
- **Deciders:** project owner

## Context

[ADR-0013](0013-gold-star-schema.md) specified the Gold layer *shape* — 6 facts, 3 dims, 2 aggregates, surrogate keys, and a `pit_join_company` point-in-time macro — but it was written before any dbt model existed and could not anticipate how the actual Silver data and DLT semantics would constrain the implementation. Building the 11 tables on `feat/gold-dbt-foundation` surfaced four points where the literal ADR-0013 spec was either wrong for the data or under-specified. This ADR records those refinements so the decision log matches the shipped code; it does not change the star-schema shape ADR-0013 defined.

The four forces, all discovered during implementation and verified against the live `silver.fmp` tables via `dbt show`:

1. **SCD2 interval semantics.** Silver's `company_scd2` is produced by DLT `create_auto_cdc_flow(..., stored_as_scd_type=2)`, whose `__END_AT` is an **exclusive** upper bound. ADR-0013 wrote the join as `event_date BETWEEN scd_effective_from AND COALESCE(scd_effective_to, …)` — an inclusive-both-ends `BETWEEN`, which double-counts the boundary day when a record closes.
2. **SCD2 single-snapshot initial load.** Silver was populated from a single ingestion batch, so every company's `__START_AT` is the load date (2026-05-21), not the start of business history. A point-in-time join keyed on that date returns `NULL` for all price/event history before 2026-05-21 (verified: `min(price_date)=2021-05-24` vs `min(scd_effective_from)=2026-05-21`).
3. **Conformed-dimension date range.** `dim_date` was initially `2015-01-01 → 2030-12-31`, but corporate-action history reaches far earlier (`splits` to 1967-06-19, `dividends` to 1970-02-16, `earnings` to 1985-09-30). A conformed date dimension must span every date any fact emits.
4. **Fact materialization uniformity.** ADR-0013 and the CLAUDE.md conventions imply all facts are `incremental`. Two of the six facts source from FMP's 5-record-capped, static fundamentals — incremental + lookback machinery there is meaningless.

## Decision

We refine the ADR-0013 implementation as follows:

1. **`pit_join_company` uses a half-open interval**, not `BETWEEN`: `fact.event_date >= dim.scd_effective_from AND fact.event_date < COALESCE(dim.scd_effective_to, DATE '9999-12-31')`. This matches DLT's exclusive `__END_AT` and avoids boundary double-attribution. (`macros/pit_join_company.sql`.)
2. **`dim_company` floors each symbol's earliest SCD2 segment to `DATE '1900-01-01'`** via `case when __START_AT = min(__START_AT) over (partition by symbol) then date '1900-01-01' else to_date(__START_AT,'yyyyMMdd') end`. Only the earliest segment is backdated; later segments (when Silver ever produces real multi-segment history) keep their true boundaries. (`models/marts/core/dim_company.sql`.)
3. **`dim_date` spans `1960-01-01 → 2030-12-31`** (25,932 contiguous rows) so every event `date_key` resolves. The `nyse_holidays` seed is **left scoped to 2015–2030 by design**: no fact relies on pre-2015 trading-day semantics (prices begin 2021; aggregates roll up prices; events only need `date_key` to exist), so pre-2015 rows carry `is_holiday=false` / weekday-only `is_market_open`. (`models/marts/core/dim_date.sql`, `seeds/nyse_holidays.csv`.)
4. **Fact materialization follows volume/cadence, not uniformity:** `incremental` (`merge` + lookback) for append-growing facts — `fact_stock_daily` (7-day lookback) and the three event facts (90-day lookback); `table` for the bounded/static fundamentals facts — `fact_financial_statement`, `fact_key_metric` — and both aggregates.

## Considered alternatives

- **Keep `BETWEEN` (ADR-0013 literal)** — rejected: inclusive-both-ends double-attributes the boundary day under DLT's exclusive `__END_AT`. Untestable today (all `__END_AT` are NULL) but wrong the moment a second segment appears.
- **Leave `dim_company` un-floored; accept NULL `company_key` for history** — rejected: ~99% of `fact_stock_daily` and all pre-load events would have no company linked; the `not_null` FK test would fail. Point-in-time-pure but useless for a single-snapshot dataset.
- **Filter facts to `event_date >= 2015` instead of extending `dim_date`** — rejected: discards genuine dividend/split history (1967–2014), gutting the corporate-action narrative the ticker universe (PYPL, NVDA, JNJ) was chosen to exercise.
- **Regenerate the holiday seed for 1960–2030** — considered; deferred. `pandas_market_calendars` supports it, but no downstream consumer needs pre-2015 holiday accuracy; the marginal correctness doesn't justify the seed churn now.
- **Force all six facts `incremental` for uniformity** — rejected: a lookback window on a 50-row, never-growing source is cargo-culting. The volume/cadence split ("incremental ⟺ append-growing") is the more defensible engineering story.

## Consequences

- **Positive:** Shipped code matches a written decision; the `pit_join_company` macro is point-in-time-correct under real DLT semantics; every FK (`company_key`, `date_key`) resolves with zero nulls across all 6 facts + 2 aggregates (verified at CP12, full `dbt build` `PASS=125 ERROR=0`). The materialization split reads as deliberate judgment in review.
- **Negative / cost:** The `1900-01-01` floor asserts the single 2026-05-21 profile snapshot applies retroactively to all history — a documented fiction, acceptable only because Silver has one snapshot. Pre-2015 `dim_date` rows have approximate (`holiday=false`) market-open flags. The half-open boundary remains untested until Silver produces a closed SCD2 segment (`__END_AT` non-NULL).
- **Follow-ups required:** If Silver later produces real multi-segment `company_scd2` history, revisit the `1900-01-01` floor (it should apply only to the genuine first segment, which the `min(__START_AT) over (partition by symbol)` guard already handles). Holiday-seed extension to 1960 is a candidate cleanup if any pre-2015 trading-day metric is ever needed. CI/CD productionization (prod target → `gold.marts`, docs → GitHub Pages) remains deferred to `feat/ci-cd`.

## References

- [ADR-0013](0013-gold-star-schema.md) — the Gold star-schema shape this ADR refines (not supersedes).
- [ADR-0002](0002-medallion-layer-ownership.md) — Gold consumes Silver; Silver owns SCD2.
- [ADR-0011](0011-fmp-fundamentals-five-record-cap.md) — the 5-record cap that makes the fundamentals facts static (→ `table`).
- `macros/pit_join_company.sql`, `models/marts/core/{dim_company,dim_date}.sql`, `models/marts/finance/*.sql` — the implementing code.
- Plan file `~/.claude/plans/feat-gold-dbt.md` — CP4/CP5/CP7/CP10 verification trail.
