{{ config(materialized='table') }}

with scd2 as (
    select * from {{ source('silver', 'company_scd2') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['symbol', '__START_AT']) }}  as company_key,
    symbol,
    companyName                                       as company_name,
    sector,
    industry,
    exchange,
    exchangeFullName                                  as exchange_full_name,
    country,
    currency,
    ipoDate                                           as ipo_date,
    ceo,
    fullTimeEmployees                                 as full_time_employees,
    isActivelyTrading                                 as is_actively_trading,
    isEtf                                             as is_etf,
    isAdr                                             as is_adr,
        case
        when __START_AT = min(__START_AT) over (partition by symbol)
        then date '1900-01-01'
        else to_date(__START_AT, 'yyyyMMdd')
    end                                               as scd_effective_from,
    to_date(__END_AT,   'yyyyMMdd')                   as scd_effective_to,
    case when to_date(__END_AT, 'yyyyMMdd') is null then true else false end as is_current
from scd2