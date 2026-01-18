import os
import json

def write_channel_messages_json(base_path: str, date_str: str, channel_name: str, messages: list):
    """
    Write channel messages to JSON file partitioned by date.
    Format: data/raw/telegram_messages/YYYY-MM-DD/channel_name.json
    """
    json_dir = os.path.join(base_path, "raw", "telegram_messages", date_str)
    os.makedirs(json_dir, exist_ok=True)
    file_path = os.path.join(json_dir, f"{channel_name}.json")
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(messages, f, ensure_ascii=False, indent=4)

def write_manifest(base_path: str, date_str: str, channel_message_counts: dict):
    """
    Write a manifest file with scraping metadata.
    """
    manifest_dir = os.path.join(base_path, "raw", "telegram_messages", date_str)
    os.makedirs(manifest_dir, exist_ok=True)
    manifest_path = os.path.join(manifest_dir, "_manifest.json")
    
    manifest = {
        "scraped_date": date_str,
        "channel_counts": channel_message_counts,
        "total_messages": sum(channel_message_counts.values())
    }
    
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=4)