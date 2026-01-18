from pydantic import BaseModel
from typing import List, Optional
from datetime import date


# Request/Response schemas for API validation

class ChannelInfo(BaseModel):
    channel_key: str
    channel_id: int
    channel_name: str
    channel_type: str
    total_posts: int
    avg_views: float
    first_post_date: Optional[date]
    last_post_date: Optional[date]

    class Config:
        from_attributes = True


class MessageInfo(BaseModel):
    message_id: int
    channel_name: str
    message_text: Optional[str]
    message_length: int
    view_count: int
    forward_count: int
    has_image: bool
    message_date: Optional[str]

    class Config:
        from_attributes = True


class TopProductResponse(BaseModel):
    term: str
    mention_count: int
    avg_views: float
    avg_forwards: float


class ChannelActivityResponse(BaseModel):
    channel_name: str
    total_posts: int
    avg_views: float
    avg_forwards: float
    posts_with_images: int
    image_percentage: float
    date_range: str


class MessageSearchResponse(BaseModel):
    total_results: int
    messages: List[MessageInfo]


class VisualContentStats(BaseModel):
    total_messages: int
    messages_with_images: int
    image_percentage: float
    by_category: dict
    by_channel: dict


class ImageDetectionStats(BaseModel):
    message_id: int
    detected_class: Optional[str]
    confidence_score: Optional[float]
    image_category: str
    channel_name: str


class PaginationParams(BaseModel):
    limit: int = 20
    offset: int = 0

    class Config:
        json_schema_extra = {
            "example": {
                "limit": 20,
                "offset": 0,
            }
        }
