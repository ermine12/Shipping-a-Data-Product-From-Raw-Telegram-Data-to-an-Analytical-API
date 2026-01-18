with base as (
    select
        channel_id,
        coalesce(channel_username, channel_name) as channel_name,
        min(message_ts) as first_post_date,
        max(message_ts) as last_post_date,
        count(*) as total_posts,
        avg(nullif(view_count,0)) as avg_views
    from {{ ref('stg_telegram_messages') }}
    group by 1,2
)
select
    {{ dbt_utils.generate_surrogate_key(['channel_id']) }} as channel_key,
    channel_id,
    channel_name,
    case
        when lower(channel_name) like '%pharma%' then 'Pharmaceutical'
        when lower(channel_name) like '%cosmetic%' then 'Cosmetics'
        when lower(channel_name) like '%medic%' then 'Medical'
        else 'Unknown'
    end as channel_type,
    first_post_date::date as first_post_date,
    last_post_date::date as last_post_date,
    total_posts,
    avg_views
from base;