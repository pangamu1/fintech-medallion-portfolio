{{ config(materialized='table') }}

with calendar as (

    {{ dbt_date.get_date_dimension("1960-01-01", "2030-12-31") }}

),

holidays as (
    select holiday_date from {{ ref('nyse_holidays') }}
)

select
    cast(date_format(c.date_day, 'yyyyMMdd') as int)        as date_key,
    c.date_day,
    c.day_of_week,
    c.day_of_week_name,
    c.day_of_month,
    c.day_of_year,
    c.week_of_year,
    c.week_start_date,
    c.week_end_date,
    c.month_of_year,
    c.month_name,
    c.month_name_short,
    c.month_start_date,
    c.month_end_date,
    c.quarter_of_year,
    concat('Q', cast(c.quarter_of_year as string))          as quarter_name,
    c.quarter_start_date,
    c.quarter_end_date,
    c.year_number,
    case when dayofweek(c.date_day) in (1, 7) then false else true end       as is_weekday,
    case when h.holiday_date is not null then true else false end            as is_holiday,
    case when dayofweek(c.date_day) in (1, 7) then false
         when h.holiday_date is not null then false
         else true end                                      as is_market_open
from calendar c
left join holidays h on c.date_day = h.holiday_date 