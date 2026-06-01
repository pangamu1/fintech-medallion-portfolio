{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key=['symbol', 'event_date']
    )
}}

with earnings as (
    select * from {{ source('silver', 'earnings') }}

    {% if is_incremental() %}
    where event_date >= (select date_sub(max(event_date), 90) from {{ this }})
    {% endif %}
)

select
    cast(date_format(e.event_date, 'yyyyMMdd') as int)   as date_key,
    dim_co.company_key,
    e.symbol,
    e.event_date,
    e.epsActual                          as eps_actual,
    e.epsEstimated                       as eps_estimated,
    e.epsActual - e.epsEstimated         as eps_surprise,
    e.revenueActual                      as revenue_actual,
    e.revenueEstimated                   as revenue_estimated,
    e.revenueActual - e.revenueEstimated as revenue_surprise
from earnings e
{{ pit_join_company('e', 'event_date') }}