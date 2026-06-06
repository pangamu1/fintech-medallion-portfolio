{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key=['accession', 'transaction_table', 'line_index']
    )
}}

with insider as (
    select * from {{ source('silver_sec', 'insider_transactions') }}

    {% if is_incremental() %}
    where transaction_date >= (select date_sub(max(transaction_date), 90) from {{ this }})
    {% endif %}
)

select
    cast(date_format(i.transaction_date, 'yyyyMMdd') as int)  as date_key,
    dim_co.company_key,
    i.ticker                          as symbol,
    i.accession,
    i.`table`                         as transaction_table,
    i.line_index,
    i.transaction_date,
    i.rpt_owner_cik,
    i.rpt_owner_name,
    i.is_director,
    i.is_officer,
    i.officer_title,
    i.is_ten_percent_owner,
    i.security_title,
    i.transaction_code,
    i.transaction_shares,
    i.transaction_price_per_share,
    i.acquired_disposed_code,
    i.shares_owned_following,
    i.direct_or_indirect,
    i.conversion_or_exercise_price,
    i.exercise_date,
    i.expiration_date,
    i.underlying_security_title,
    i.underlying_security_shares
from insider i
{{ pit_join_company('i', 'transaction_date', symbol_column='ticker') }}