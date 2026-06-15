{{ config(materialized='table') }}

with daily as (
    select
        f.company_key,
        f.symbol,
        c.sector,
        f.price_date,
        f.open_price,
        f.high_price,
        f.low_price,
        f.close_price,
        f.volume,
        f.adj_close
    from {{ ref('fact_stock_daily') }} f
    inner join {{ ref('dim_company') }} c on f.company_key = c.company_key
)

select
    company_key,
    symbol,
    sector,
    cast(date_format(price_date, 'yyyyMM') as int)  as year_month,
    trunc(price_date, 'MM')                         as month_start_date,
    min_by(open_price, price_date)                  as monthly_open,
    max(high_price)                                 as monthly_high,
    min(low_price)                                  as monthly_low,
    max_by(close_price, price_date)                 as monthly_close,
    max_by(adj_close, price_date)                   as monthly_adj_close,
    sum(volume)                                     as monthly_volume,
    avg(close_price)                                as avg_close,
    count(*)                                        as trading_days
from daily
group by company_key, symbol, sector, year_month, month_start_date