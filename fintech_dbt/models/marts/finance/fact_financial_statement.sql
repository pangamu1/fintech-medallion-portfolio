with income as (
    select symbol, fiscalYear, period, period_end_date,
        'income_statement' as statement_type,
                stack(12,
            'revenue',           cast(revenue           as double),
            'costOfRevenue',     cast(costOfRevenue     as double),
            'grossProfit',       cast(grossProfit       as double),
            'operatingExpenses', cast(operatingExpenses as double),
            'operatingIncome',   cast(operatingIncome   as double),
            'ebitda',            cast(ebitda            as double),
            'incomeBeforeTax',   cast(incomeBeforeTax   as double),
            'incomeTaxExpense',  cast(incomeTaxExpense  as double),
            'netIncome',         cast(netIncome         as double),
            'eps',               cast(eps               as double),
            'epsDiluted',        cast(epsDiluted        as double),
            'interestExpense',   cast(interestExpense   as double)
        ) as (line_item, line_item_value)
    from {{ source('silver', 'income_statement') }}
),

balance as (
    select symbol, fiscalYear, period, period_end_date,
        'balance_sheet' as statement_type,
                stack(12,
            'totalAssets',             cast(totalAssets             as double),
            'totalCurrentAssets',      cast(totalCurrentAssets      as double),
            'cashAndCashEquivalents',  cast(cashAndCashEquivalents  as double),
            'inventory',               cast(inventory               as double),
            'netReceivables',          cast(netReceivables          as double),
            'totalLiabilities',        cast(totalLiabilities        as double),
            'totalCurrentLiabilities', cast(totalCurrentLiabilities as double),
            'longTermDebt',            cast(longTermDebt            as double),
            'totalDebt',               cast(totalDebt               as double),
            'netDebt',                 cast(netDebt                 as double),
            'totalStockholdersEquity', cast(totalStockholdersEquity as double),
            'retainedEarnings',        cast(retainedEarnings        as double)
        ) as (line_item, line_item_value)
    from {{ source('silver', 'balance_sheet') }}
),

cashflow as (
    select symbol, fiscalYear, period, period_end_date,
        'cash_flow' as statement_type,
                stack(10,
            'operatingCashFlow',           cast(operatingCashFlow           as double),
            'freeCashFlow',                cast(freeCashFlow                as double),
            'capitalExpenditure',          cast(capitalExpenditure          as double),
            'netIncome',                   cast(netIncome                   as double),
            'depreciationAndAmortization', cast(depreciationAndAmortization as double),
            'changeInWorkingCapital',      cast(changeInWorkingCapital      as double),
            'netChangeInCash',             cast(netChangeInCash             as double),
            'commonDividendsPaid',         cast(commonDividendsPaid         as double),
            'netDividendsPaid',            cast(netDividendsPaid            as double),
            'stockBasedCompensation',      cast(stockBasedCompensation      as double)
        ) as (line_item, line_item_value)
    from {{ source('silver', 'cash_flow') }}
),

unioned as (
    select * from income
    union all
    select * from balance
    union all
    select * from cashflow
)

select
    fp.fiscal_period_key,
    fp.period_end_date_key,
    dim_co.company_key,
    u.symbol,
    cast(u.fiscalYear as int)         as fiscal_year,
    u.period                          as fiscal_period,
    u.statement_type,
    u.line_item,
    cast(u.line_item_value as double) as line_item_value
from unioned u
left join {{ ref('dim_fiscal_period') }} fp
    on  u.symbol                  = fp.symbol
    and cast(u.fiscalYear as int) = fp.fiscal_year
    and u.period                  = fp.fiscal_period
{{ pit_join_company('u', 'period_end_date') }}