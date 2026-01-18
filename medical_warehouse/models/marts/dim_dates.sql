with dates as (
    select
        generate_series(
            (select min(date_trunc('day', message_ts)) from {{ ref('stg_telegram_messages') }}),
            (select max(date_trunc('day', message_ts)) from {{ ref('stg_telegram_messages') }}),
            interval '1 day'
        )::date as full_date
)
select
    to_char(full_date, 'YYYYMMDD')::int as date_key,
    full_date,
    extract(isodow from full_date)::int as day_of_week,
    to_char(full_date, 'Day')::text as day_name,
    extract(week from full_date)::int as week_of_year,
    extract(month from full_date)::int as month,
    to_char(full_date, 'Month')::text as month_name,
    extract(quarter from full_date)::int as quarter,
    extract(year from full_date)::int as year,
    case when extract(isodow from full_date) in (6,7) then true else false end as is_weekend
from dates
order by full_date;