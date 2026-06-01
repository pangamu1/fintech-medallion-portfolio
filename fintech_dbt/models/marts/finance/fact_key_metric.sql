with key_metrics as (
    select * from {{ source('silver', 'key_metrics') }}
)

select
    fp.fiscal_period_key,
    fp.period_end_date_key,
    dim_co.company_key,
    km.symbol,
    cast(km.fiscalYear as int)  as fiscal_year,
    km.period                   as fiscal_period,
    km.marketCap                as market_cap,
    km.enterpriseValue          as enterprise_value,
    km.evToEBITDA               as ev_to_ebitda,
    km.evToSales                as ev_to_sales,
    km.evToFreeCashFlow         as ev_to_free_cash_flow,
    km.earningsYield            as earnings_yield,
    km.freeCashFlowYield        as free_cash_flow_yield,
    km.returnOnEquity           as return_on_equity,
    km.returnOnAssets           as return_on_assets,
    km.returnOnInvestedCapital  as return_on_invested_capital,
    km.returnOnCapitalEmployed  as return_on_capital_employed,
    km.currentRatio             as current_ratio,
    km.netDebtToEBITDA          as net_debt_to_ebitda,
    km.workingCapital           as working_capital,
    km.investedCapital          as invested_capital,
    km.incomeQuality            as income_quality
from key_metrics km
left join {{ ref('dim_fiscal_period') }} fp
    on  km.symbol                  = fp.symbol
    and cast(km.fiscalYear as int) = fp.fiscal_year
    and km.period                  = fp.fiscal_period
{{ pit_join_company('km', 'period_end_date') }}