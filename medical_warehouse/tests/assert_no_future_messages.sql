-- Fails if any messages appear to be in the future relative to now()
select 1
from {{ ref('stg_telegram_messages') }}
where message_ts > now()
limit 1;