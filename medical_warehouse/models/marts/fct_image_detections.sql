with detections as (
    select
        message_id,
        image_path,
        detected_class,
        confidence_score,
        image_category,
        all_detections,
        processed_at
    from raw.cv_detections
)
select
    d.message_id,
    {{ dbt_utils.generate_surrogate_key(['m.channel_id']) }} as channel_key,
    to_char(m.message_ts::date, 'YYYYMMDD')::int as date_key,
    d.detected_class,
    d.confidence_score,
    d.image_category,
    d.all_detections,
    d.processed_at
from detections d
left join {{ ref('stg_telegram_messages') }} m on d.message_id = m.message_id
where d.message_id is not null;