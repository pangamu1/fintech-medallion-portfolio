{{ config(materialized='table') }}

with fundamentals as (
    select symbol, fiscalYear, period, period_end_date from {{ source('silver','income_statement') }}
    union all
    select symbol, fiscalYear, period, period_end_date from {{ source('silver','balance_sheet') }}
    union all
    select symbol, fiscalYear, period, period_end_date from {{ source('silver','cash_flow') }}
    union all
    select symbol, fiscalYear, period, period_end_date from {{ source('silver','key_metrics') }}
),

deduped as (
    select
        symbol,
        cast(fiscalYear as int) as fiscal_year,
        period                  as fiscal_period,
        max(period_end_date)    as period_end_date
    from fundamentals
    group by symbol, fiscalYear, period
)

select
    {{ dbt_utils.generate_surrogate_key(['symbol', 'fiscal_year', 'fiscal_period']) }} as fiscal_period_key,
    symbol,
    fiscal_year,
    fiscal_period,
    period_end_date,
    cast(date_format(period_end_date, 'yyyyMMdd') as int) as period_end_date_key
from deduped