with base as (
    select * from {{ ref('stg_telegram_messages') }}
)
select
    message_id,
    -- FK to dim_channels
    {{ dbt_utils.generate_surrogate_key(['channel_id']) }} as channel_key,
    -- FK to dim_dates
    to_char(message_ts::date, 'YYYYMMDD')::int as date_key,
    message_text,
    message_length,
    view_count,
    forward_count,
    has_image
from base;