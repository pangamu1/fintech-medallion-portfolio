{{ config(materialized='table') }}

with daily as (
    select
        f.date_key,
        f.price_date,
        c.sector,
        f.symbol,
        f.close_price,
        f.volume,
        f.change_percent
    from {{ ref('fact_stock_daily') }} f
    inner join {{ ref('dim_company') }} c on f.company_key = c.company_key
)

select
    sector,
    date_key,
    price_date              as trade_date,
    count(distinct symbol)  as company_count,
    sum(volume)             as total_volume,
    avg(close_price)        as avg_close,
    avg(change_percent)     as avg_change_percent
from daily
group by sector, date_key, price_date