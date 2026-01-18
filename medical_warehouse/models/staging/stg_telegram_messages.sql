with source as (
    select
        message_id,
        channel_id,
        coalesce(nullif(trim(channel_username), ''), null) as channel_username,
        coalesce(nullif(trim(channel_name), ''), null) as channel_name,
        message_text,
        cast(message_date as timestamp) as message_ts,
        cast(view_count as bigint) as view_count,
        cast(forward_count as bigint) as forward_count,
        cast(has_image as boolean) as has_image,
        raw_payload
    from raw.telegram_messages
), cleaned as (
    select
        message_id::bigint as message_id,
        channel_id::bigint as channel_id,
        channel_username,
        channel_name,
        nullif(message_text, '') as message_text,
        message_ts,
        view_count,
        forward_count,
        has_image,
        length(coalesce(message_text, '')) as message_length,
        raw_payload
    from source
    where message_id is not null
      and message_ts is not null
      and (message_text is not null and message_text <> '')
)
select * from cleaned;
