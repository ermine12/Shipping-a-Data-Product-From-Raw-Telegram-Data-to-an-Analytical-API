from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
import logging

from .database import get_db
from .schemas import (
    TopProductResponse,
    ChannelActivityResponse,
    MessageSearchResponse,
    VisualContentStats,
    ImageDetectionStats,
    MessageInfo,
    ChannelInfo,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Medical Telegram Warehouse API",
    version="1.0.0",
    description="Analytical API for Telegram medical channel data",
    docs_url="/docs",
    openapi_url="/openapi.json",
)


@app.get("/", tags=["Health"])
def read_root():
    """Root endpoint - API status."""
    return {"message": "Welcome to Medical Telegram Warehouse API", "version": "1.0.0"}


@app.get("/health", tags=["Health"])
def health(db: Session = Depends(get_db)):
    """Health check endpoint."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Database connection failed")


@app.get("/api/reports/top-products", response_model=list[TopProductResponse], tags=["Reports"])
def get_top_products(
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Returns the most frequently mentioned terms/products across all channels.
    
    - **limit**: Number of top products to return (1-100)
    """
    try:
        query = text("""
            WITH word_freq AS (
                SELECT
                    lower(unnest(string_to_array(message_text, ' '))) as term,
                    view_count,
                    forward_count
                FROM public.fct_messages
                WHERE message_text IS NOT NULL
                  AND length(message_text) > 0
            ),
            filtered_terms AS (
                SELECT
                    term,
                    COUNT(*) as mention_count,
                    AVG(view_count) as avg_views,
                    AVG(forward_count) as avg_forwards
                FROM word_freq
                WHERE length(term) > 3
                  AND term NOT IN ('the', 'and', 'for', 'with', 'from', 'that', 'this', 'have', 'been', 'are')
                GROUP BY term
                HAVING COUNT(*) > 5
            )
            SELECT
                term,
                mention_count,
                ROUND(avg_views::numeric, 2) as avg_views,
                ROUND(avg_forwards::numeric, 2) as avg_forwards
            FROM filtered_terms
            ORDER BY mention_count DESC
            LIMIT :limit
        """)
        
        results = db.execute(query, {"limit": limit}).fetchall()
        return [
            TopProductResponse(
                term=r[0],
                mention_count=r[1],
                avg_views=float(r[2]),
                avg_forwards=float(r[3]),
            )
            for r in results
        ]
    except Exception as e:
        logger.error(f"Error fetching top products: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch top products")


@app.get("/api/channels/{channel_name}/activity", response_model=ChannelActivityResponse, tags=["Channels"])
def get_channel_activity(
    channel_name: str,
    db: Session = Depends(get_db),
):
    """
    Returns posting activity and trends for a specific channel.
    
    - **channel_name**: Name or username of the Telegram channel
    """
    try:
        query = text("""
            SELECT
                dc.channel_name,
                COUNT(fm.message_id) as total_posts,
                ROUND(AVG(fm.view_count)::numeric, 2) as avg_views,
                ROUND(AVG(fm.forward_count)::numeric, 2) as avg_forwards,
                COUNT(CASE WHEN fm.has_image THEN 1 END) as posts_with_images,
                ROUND(
                    100.0 * COUNT(CASE WHEN fm.has_image THEN 1 END) / COUNT(fm.message_id),
                    2
                ) as image_percentage,
                MIN(dd.full_date)::text || ' to ' || MAX(dd.full_date)::text as date_range
            FROM public.fct_messages fm
            JOIN public.dim_channels dc ON fm.channel_key = dc.channel_key
            JOIN public.dim_dates dd ON fm.date_key = dd.date_key
            WHERE LOWER(dc.channel_name) LIKE LOWER(:channel_name)
            GROUP BY dc.channel_name
        """)
        
        result = db.execute(query, {"channel_name": f"%{channel_name}%"}).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Channel '{channel_name}' not found")
        
        return ChannelActivityResponse(
            channel_name=result[0],
            total_posts=result[1],
            avg_views=float(result[2]),
            avg_forwards=float(result[3]),
            posts_with_images=result[4],
            image_percentage=float(result[5]),
            date_range=result[6],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching channel activity: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch channel activity")


@app.get("/api/search/messages", response_model=MessageSearchResponse, tags=["Search"])
def search_messages(
    query: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Searches for messages containing a specific keyword.
    
    - **query**: Search term (case-insensitive)
    - **limit**: Number of results to return (1-100)
    - **offset**: Pagination offset
    """
    try:
        count_query = text("""
            SELECT COUNT(*)
            FROM public.fct_messages
            WHERE message_text ILIKE :query
        """)
        
        total = db.execute(count_query, {"query": f"%{query}%"}).scalar()
        
        search_query = text("""
            SELECT
                fm.message_id,
                dc.channel_name,
                fm.message_text,
                fm.message_length,
                fm.view_count,
                fm.forward_count,
                fm.has_image,
                dd.full_date::text
            FROM public.fct_messages fm
            JOIN public.dim_channels dc ON fm.channel_key = dc.channel_key
            JOIN public.dim_dates dd ON fm.date_key = dd.date_key
            WHERE fm.message_text ILIKE :query
            ORDER BY fm.view_count DESC
            LIMIT :limit OFFSET :offset
        """)
        
        results = db.execute(
            search_query,
            {"query": f"%{query}%", "limit": limit, "offset": offset},
        ).fetchall()
        
        messages = [
            MessageInfo(
                message_id=r[0],
                channel_name=r[1],
                message_text=r[2],
                message_length=r[3],
                view_count=r[4],
                forward_count=r[5],
                has_image=r[6],
                message_date=r[7],
            )
            for r in results
        ]
        
        return MessageSearchResponse(total_results=total, messages=messages)
    except Exception as e:
        logger.error(f"Error searching messages: {e}")
        raise HTTPException(status_code=500, detail="Failed to search messages")


@app.get("/api/reports/visual-content", response_model=VisualContentStats, tags=["Reports"])
def get_visual_content_stats(db: Session = Depends(get_db)):
    """
    Returns statistics about image usage across channels.
    Includes breakdown by image category and channel.
    """
    try:
        # Overall stats
        overall_query = text("""
            SELECT
                COUNT(*) as total_messages,
                COUNT(CASE WHEN has_image THEN 1 END) as messages_with_images,
                ROUND(
                    100.0 * COUNT(CASE WHEN has_image THEN 1 END) / COUNT(*),
                    2
                ) as image_percentage
            FROM public.fct_messages
        """)
        
        overall = db.execute(overall_query).fetchone()
        
        # By category
        category_query = text("""
            SELECT
                CASE WHEN has_image THEN 'with_image' ELSE 'without_image' END as category,
                COUNT(*) as count
            FROM public.fct_messages
            GROUP BY category
        """)
        
        category_results = db.execute(category_query).fetchall()
        by_category = {r[0]: r[1] for r in category_results}
        
        # By channel
        channel_query = text("""
            SELECT
                dc.channel_name,
                COUNT(*) as total,
                COUNT(CASE WHEN fm.has_image THEN 1 END) as with_images,
                ROUND(
                    100.0 * COUNT(CASE WHEN fm.has_image THEN 1 END) / COUNT(*),
                    2
                ) as image_pct
            FROM public.fct_messages fm
            JOIN public.dim_channels dc ON fm.channel_key = dc.channel_key
            GROUP BY dc.channel_name
            ORDER BY image_pct DESC
            LIMIT 20
        """)
        
        channel_results = db.execute(channel_query).fetchall()
        by_channel = {
            r[0]: {"total": r[1], "with_images": r[2], "image_percentage": float(r[3])}
            for r in channel_results
        }
        
        return VisualContentStats(
            total_messages=overall[0],
            messages_with_images=overall[1],
            image_percentage=float(overall[2]),
            by_category=by_category,
            by_channel=by_channel,
        )
    except Exception as e:
        logger.error(f"Error fetching visual content stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch visual content stats")


@app.get("/api/reports/image-detections", response_model=list[ImageDetectionStats], tags=["Reports"])
def get_image_detections(
    limit: int = Query(50, ge=1, le=500),
    image_category: str = Query(None, description="Filter by image category (promotional, product_display, lifestyle, other)"),
    db: Session = Depends(get_db),
):
    """
    Returns YOLO image detection results with confidence scores.
    
    - **limit**: Number of results to return
    - **image_category**: Optional filter by image category
    """
    try:
        where_clause = "WHERE fid.message_id IS NOT NULL"
        params = {"limit": limit}
        
        if image_category:
            where_clause += " AND fid.image_category = :image_category"
            params["image_category"] = image_category
        
        query = text(f"""
            SELECT
                fid.message_id,
                fid.detected_class,
                fid.confidence_score,
                fid.image_category,
                dc.channel_name
            FROM public.fct_image_detections fid
            LEFT JOIN public.dim_channels dc ON fid.channel_key = dc.channel_key
            {where_clause}
            ORDER BY fid.confidence_score DESC NULLS LAST
            LIMIT :limit
        """)
        
        results = db.execute(query, params).fetchall()
        
        return [
            ImageDetectionStats(
                message_id=r[0],
                detected_class=r[1],
                confidence_score=float(r[2]) if r[2] else None,
                image_category=r[3],
                channel_name=r[4],
            )
            for r in results
        ]
    except Exception as e:
        logger.error(f"Error fetching image detections: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch image detections")


@app.get("/api/channels", response_model=list[ChannelInfo], tags=["Channels"])
def list_channels(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """
    Returns a list of all channels with aggregated statistics.
    
    - **limit**: Maximum number of channels to return
    """
    try:
        query = text("""
            SELECT
                channel_key,
                channel_id,
                channel_name,
                channel_type,
                total_posts,
                COALESCE(avg_views, 0) as avg_views,
                first_post_date,
                last_post_date
            FROM public.dim_channels
            ORDER BY total_posts DESC
            LIMIT :limit
        """)
        
        results = db.execute(query, {"limit": limit}).fetchall()
        
        return [
            ChannelInfo(
                channel_key=str(r[0]),
                channel_id=r[1],
                channel_name=r[2],
                channel_type=r[3],
                total_posts=r[4],
                avg_views=float(r[5]),
                first_post_date=r[6],
                last_post_date=r[7],
            )
            for r in results
        ]
    except Exception as e:
        logger.error(f"Error fetching channels: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch channels")


@app.get("/api/reports/top-messages", tags=["Reports"])
def get_top_messages(
    limit: int = Query(20, ge=1, le=100),
    days: int = Query(30, ge=1, le=365, description="Look back N days"),
    db: Session = Depends(get_db),
):
    """
    Returns top messages by engagement (views + forwards) within a time window.
    
    - **limit**: Number of top messages to return
    - **days**: Number of days to look back
    """
    try:
        query = text("""
            SELECT
                fm.message_id,
                dc.channel_name,
                fm.message_text,
                fm.view_count,
                fm.forward_count,
                (fm.view_count + fm.forward_count) as engagement,
                dd.full_date::text
            FROM public.fct_messages fm
            JOIN public.dim_channels dc ON fm.channel_key = dc.channel_key
            JOIN public.dim_dates dd ON fm.date_key = dd.date_key
            WHERE dd.full_date >= CURRENT_DATE - INTERVAL '1 day' * :days
            ORDER BY engagement DESC
            LIMIT :limit
        """)
        
        results = db.execute(query, {"limit": limit, "days": days}).fetchall()
        
        return [
            {
                "message_id": r[0],
                "channel_name": r[1],
                "message_text": r[2][:100] + "..." if len(r[2]) > 100 else r[2],
                "view_count": r[3],
                "forward_count": r[4],
                "engagement": r[5],
                "date": r[6],
            }
            for r in results
        ]
    except Exception as e:
        logger.error(f"Error fetching top messages: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch top messages")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
