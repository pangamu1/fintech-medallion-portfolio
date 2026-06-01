{% macro pit_join_company(fact_alias, event_date_column, symbol_column='symbol', dim_alias='dim_co') %}
-- Point-in-time SCD2 join: attaches dim_company.company_key valid on the fact's event_date.
-- Half-open interval [scd_effective_from, scd_effective_to); current row is open-ended via coalesce.
left join {{ ref('dim_company') }} as {{ dim_alias }}
    on  {{ fact_alias }}.{{ symbol_column }}     =  {{ dim_alias }}.symbol
    and {{ fact_alias }}.{{ event_date_column }} >= {{ dim_alias }}.scd_effective_from
    and {{ fact_alias }}.{{ event_date_column }} <  coalesce({{ dim_alias }}.scd_effective_to, date '9999-12-31')
{% endmacro %}