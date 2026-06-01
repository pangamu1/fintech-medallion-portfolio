{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key=['symbol', 'event_date']
    )
}}

with splits as (
    select * from {{ source('silver', 'splits') }}

    {% if is_incremental() %}
    where event_date >= (select date_sub(max(event_date), 90) from {{ this }})
    {% endif %}
)

select
    cast(date_format(s.event_date, 'yyyyMMdd') as int)   as date_key,
    dim_co.company_key,
    s.symbol,
    s.event_date,
    s.numerator,
    s.denominator,
    cast(s.numerator as double) / nullif(cast(s.denominator as double), 0) as split_ratio,
    s.splitType        as split_type
from splits s
{{ pit_join_company('s', 'event_date') }}