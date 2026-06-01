{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key=['symbol', 'event_date']
    )
}}

with dividends as (
    select * from {{ source('silver', 'dividends') }}

    {% if is_incremental() %}
    where event_date >= (select date_sub(max(event_date), 90) from {{ this }})
    {% endif %}
)

select
    cast(date_format(d.event_date, 'yyyyMMdd') as int)   as date_key,
    dim_co.company_key,
    d.symbol,
    d.event_date,
    d.dividend,
    d.adjDividend      as adj_dividend,
    d.`yield`          as dividend_yield,
    d.frequency,
    d.declarationDate  as declaration_date,
    d.recordDate       as record_date,
    d.paymentDate      as payment_date
from dividends d
{{ pit_join_company('d', 'event_date') }}