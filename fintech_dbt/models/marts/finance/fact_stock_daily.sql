{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key=['symbol', 'price_date']
    )
}}

with prices as (

    select * from {{ source('silver', 'daily_prices') }}

    {% if is_incremental() %}
    where price_date >= (select date_sub(max(price_date), 7) from {{ this }})
    {% endif %}

),

adjusted as (

    select symbol, price_date, adjClose as adj_close
    from {{ source('silver', 'daily_prices_adjusted') }}

)

select
    cast(date_format(p.price_date, 'yyyyMMdd') as int)  as date_key,
    dim_co.company_key,
    p.symbol,
    p.price_date,
    p.open                                              as open_price,
    p.high                                              as high_price,
    p.low                                               as low_price,
    p.close                                             as close_price,
    p.volume,
    p.vwap,
    p.change                                            as price_change,
    p.changePercent                                     as change_percent,
    a.adj_close
from prices p
left join adjusted a
    on  p.symbol     = a.symbol
    and p.price_date = a.price_date
{{ pit_join_company('p', 'price_date') }}