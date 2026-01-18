# Medical Telegram Data Warehouse - Complete Implementation

This document covers Tasks 3, 4, and 5: YOLO enrichment, FastAPI analytics, and Dagster orchestration.

## Architecture Overview

```
Data Lake (raw JSON/images)
    ↓
PostgreSQL Raw Schema (raw.telegram_messages, raw.cv_detections)
    ↓
dbt Staging (stg_telegram_messages, stg_cv_detections)
    ↓
dbt Marts (dim_dates, dim_channels, fct_messages, fct_image_detections)
    ↓
FastAPI Analytical Endpoints
    ↓
Dagster Orchestration (daily jobs, backfill, monitoring)
```

---

## Task 3: YOLO Object Detection

### Overview
Detects objects in Telegram message images using YOLOv8 nano model. Classifies images into categories (promotional, product_display, lifestyle, other) and enriches the warehouse.

### Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Ensure images are downloaded:**
   - Images should be in `data/raw/images/{channel_name}/{message_id}.jpg`
   - These are populated by the Telegram scraper (Task 1)

### Running YOLO Detection

```bash
python src/yolo_detect.py
```

**What it does:**
- Scans all images in `data/raw/images/`
- Runs YOLOv8 nano inference on each image
- Classifies images based on detected objects
- Saves results to `data/processed/yolo_detections.csv`
- Loads detections into PostgreSQL `raw.cv_detections` table

**Output CSV columns:**
- `message_id`: Telegram message ID
- `image_path`: Path to the image file
- `detected_class`: Top detected object class (e.g., "person", "bottle")
- `confidence_score`: Confidence of top detection (0-1)
- `image_category`: Classification (promotional, product_display, lifestyle, other)
- `all_detections`: JSON array of all detected objects
- `processed_at`: Timestamp of processing

### Image Classification Logic

| Category | Criteria |
|----------|----------|
| **promotional** | Person + bottle/container detected |
| **product_display** | Bottle/container, no person |
| **lifestyle** | Person, no product |
| **other** | Neither person nor product |

### dbt Integration

**New model:** `medical_warehouse/models/marts/fct_image_detections.sql`
- Joins detections with messages and channels
- Provides `channel_key`, `date_key`, `detected_class`, `confidence_score`, `image_category`

**New test:** `medical_warehouse/tests/assert_valid_confidence_scores.sql`
- Ensures confidence scores are between 0 and 1

### Analysis Questions

**Q: Do "promotional" posts get more views than "product_display" posts?**

```sql
SELECT
    fid.image_category,
    COUNT(*) as post_count,
    AVG(fm.view_count) as avg_views,
    AVG(fm.forward_count) as avg_forwards
FROM fct_image_detections fid
JOIN fct_messages fm ON fid.message_id = fm.message_id
WHERE fid.image_category IN ('promotional', 'product_display')
GROUP BY fid.image_category;
```

**Q: Which channels use more visual content?**

```sql
SELECT
    dc.channel_name,
    COUNT(*) as total_messages,
    COUNT(CASE WHEN fm.has_image THEN 1 END) as with_images,
    ROUND(100.0 * COUNT(CASE WHEN fm.has_image THEN 1 END) / COUNT(*), 2) as image_pct
FROM fct_messages fm
JOIN dim_channels dc ON fm.channel_key = dc.channel_key
GROUP BY dc.channel_name
ORDER BY image_pct DESC;
```

**Q: Limitations of pre-trained YOLOv8 for medical domain?**

- **General object detection:** YOLOv8 is trained on COCO dataset (everyday objects). It detects bottles, people, etc., but not specific medicines or medical devices.
- **No domain knowledge:** Cannot distinguish between pharmaceutical products, cosmetics, or medical supplies.
- **False positives:** May detect non-medical bottles as products.
- **Mitigation:** Fine-tune YOLOv8 on labeled medical product images for production use.

---

## Task 4: Analytical FastAPI

### Overview
Exposes dbt marts through REST endpoints for dashboard and application consumption.

### Setup

1. **Ensure PostgreSQL is running:**
   ```bash
   docker-compose up -d db
   ```

2. **Ensure dbt models are built:**
   ```bash
   cd medical_warehouse && dbt build
   ```

### Running the API

```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Access:**
- API: `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`
- OpenAPI schema: `http://localhost:8000/openapi.json`

### Endpoints

#### 1. Health Check
```
GET /health
```
Returns database connection status.

#### 2. Top Products
```
GET /api/reports/top-products?limit=10
```
Returns most frequently mentioned terms across all channels.

**Response:**
```json
[
  {
    "term": "paracetamol",
    "mention_count": 245,
    "avg_views": 1250.50,
    "avg_forwards": 45.30
  }
]
```

#### 3. Channel Activity
```
GET /api/channels/{channel_name}/activity
```
Returns posting activity and trends for a specific channel.

**Response:**
```json
{
  "channel_name": "Medical Supplies",
  "total_posts": 1523,
  "avg_views": 850.25,
  "avg_forwards": 32.10,
  "posts_with_images": 456,
  "image_percentage": 29.94,
  "date_range": "2025-01-01 to 2025-01-18"
}
```

#### 4. Message Search
```
GET /api/search/messages?query=paracetamol&limit=20&offset=0
```
Searches for messages containing a keyword.

**Response:**
```json
{
  "total_results": 245,
  "messages": [
    {
      "message_id": 12345,
      "channel_name": "Medical Supplies",
      "message_text": "New paracetamol stock available...",
      "message_length": 150,
      "view_count": 1250,
      "forward_count": 45,
      "has_image": true,
      "message_date": "2025-01-18"
    }
  ]
}
```

#### 5. Visual Content Stats
```
GET /api/reports/visual-content
```
Returns image usage statistics across channels.

**Response:**
```json
{
  "total_messages": 5000,
  "messages_with_images": 1200,
  "image_percentage": 24.0,
  "by_category": {
    "with_image": 1200,
    "without_image": 3800
  },
  "by_channel": {
    "Medical Supplies": {
      "total": 500,
      "with_images": 150,
      "image_percentage": 30.0
    }
  }
}
```

#### 6. Image Detections
```
GET /api/reports/image-detections?limit=50&image_category=promotional
```
Returns YOLO detection results with confidence scores.

**Response:**
```json
[
  {
    "message_id": 12345,
    "detected_class": "bottle",
    "confidence_score": 0.95,
    "image_category": "promotional",
    "channel_name": "Medical Supplies"
  }
]
```

#### 7. List Channels
```
GET /api/channels?limit=50
```
Returns all channels with aggregated statistics.

**Response:**
```json
[
  {
    "channel_key": "abc123",
    "channel_id": 123456789,
    "channel_name": "Medical Supplies",
    "channel_type": "Medical",
    "total_posts": 1523,
    "avg_views": 850.25,
    "first_post_date": "2025-01-01",
    "last_post_date": "2025-01-18"
  }
]
```

#### 8. Top Messages
```
GET /api/reports/top-messages?limit=20&days=30
```
Returns top messages by engagement within a time window.

**Response:**
```json
[
  {
    "message_id": 12345,
    "channel_name": "Medical Supplies",
    "message_text": "New paracetamol stock available...",
    "view_count": 5000,
    "forward_count": 250,
    "engagement": 5250,
    "date": "2025-01-18"
  }
]
```

### Pydantic Schemas

All request/response models are defined in `api/schemas.py`:
- `ChannelInfo`: Channel metadata
- `MessageInfo`: Message details
- `TopProductResponse`: Product mention stats
- `ChannelActivityResponse`: Channel activity summary
- `MessageSearchResponse`: Search results
- `VisualContentStats`: Image usage statistics
- `ImageDetectionStats`: YOLO detection results

### Error Handling

All endpoints return proper HTTP status codes:
- `200 OK`: Successful response
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Database or processing error

---

## Task 5: Dagster Orchestration

### Overview
Automates the entire pipeline: scraping, ingestion, enrichment, transformation, testing, and documentation.

### Setup

1. **Install Dagster:**
   ```bash
   pip install dagster dagster-webserver dagster-shell
   ```

2. **Verify pipeline file:**
   - Pipeline definition: `dagster_pipeline.py`

### Running Dagster

#### Option 1: Development Mode (Recommended)
```bash
dagster dev -f dagster_pipeline.py
```

Access Dagster UI at `http://localhost:3000`

#### Option 2: Daemon Mode (Production)
```bash
# Terminal 1: Start daemon
dagster-daemon run

# Terminal 2: Start webserver
dagster-webserver -h 0.0.0.0 -p 3000
```

### Pipeline Jobs

#### 1. Daily Ingestion Job
**Name:** `daily_ingestion_job`

**Flow:**
```
Scrape Telegram
    ↓
Load Raw to PostgreSQL
    ↓
YOLO Enrichment
    ↓
dbt Build (models + tests)
    ↓
dbt Test (data quality)
    ↓
Generate Documentation
    ↓
API Health Check
```

**Run manually:**
```bash
# In Dagster UI, click "Launchpad" → select "daily_ingestion_job" → "Launch Run"
```

**Configuration options:**
- `channels`: Comma-separated list of channels to scrape (empty = all)
- `limit`: Max messages per channel (default: 100)

#### 2. Backfill Job
**Name:** `backfill_job`

**Flow:**
```
Load Raw to PostgreSQL (skip scraping)
    ↓
YOLO Enrichment
    ↓
dbt Build
    ↓
dbt Test
    ↓
Generate Documentation
    ↓
API Health Check
```

**Use case:** Reprocess historical data without re-scraping.

#### 3. Transform-Only Job
**Name:** `transform_only_job`

**Flow:**
```
dbt Build (skip scraping and enrichment)
    ↓
dbt Test
    ↓
Generate Documentation
    ↓
API Health Check
```

**Use case:** Quick iteration on dbt models during development.

### Monitoring and Alerts

**Dagster UI Features:**
- **Runs tab:** View all pipeline runs with status (success, failure, in-progress)
- **Assets tab:** Track data assets and their lineage
- **Logs:** Detailed logs for each op
- **Backfill:** Trigger backfills for date ranges

**Failure Handling:**
- Failed ops are highlighted in red
- Click on failed op to view error logs
- Retry individual ops or entire runs

### Scheduling (Optional)

To enable daily scheduling at 2 AM UTC, uncomment in `dagster_pipeline.py`:

```python
from dagster import schedule

daily_schedule = schedule(
    job=daily_ingestion_job,
    cron_schedule="0 2 * * *",
    description="Daily ingestion at 2 AM UTC",
)
```

Then restart Dagster daemon.

### Docker Integration

**Update `docker-compose.yml` to include Dagster services:**

```yaml
services:
  db:
    image: postgres:15
    # ... existing config

  api:
    build: .
    # ... existing config

  dagster-webserver:
    build: .
    command: dagster-webserver -h 0.0.0.0 -p 3000
    ports:
      - "3000:3000"
    depends_on:
      - db
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/medical_warehouse

  dagster-daemon:
    build: .
    command: dagster-daemon run
    depends_on:
      - db
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/medical_warehouse
```

Then run:
```bash
docker-compose up -d
```

---

## End-to-End Workflow

### 1. Initial Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL
docker-compose up -d db

# Initialize dbt
cd medical_warehouse
dbt deps
dbt build
cd ..
```

### 2. Run Full Pipeline (Manual)
```bash
# Option A: Using Dagster
dagster dev -f dagster_pipeline.py
# Then trigger "daily_ingestion_job" in UI

# Option B: Manual steps
python scripts/telegram.py                    # Scrape
python scripts/load_raw_to_postgres.py        # Load raw
python src/yolo_detect.py                     # Enrich
cd medical_warehouse && dbt build && dbt test # Transform & test
cd ..
```

### 3. Query Results
```bash
# Start API
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Query endpoints
curl http://localhost:8000/api/reports/top-products?limit=10
curl http://localhost:8000/api/channels
curl http://localhost:8000/api/reports/visual-content
```

### 4. Monitor Pipeline
- Dagster UI: `http://localhost:3000`
- API Docs: `http://localhost:8000/docs`
- dbt Docs: `cd medical_warehouse && dbt docs serve`

---

## Troubleshooting

### YOLO Detection Fails
- **Issue:** Model download fails
  - **Solution:** Manually download: `python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"`
- **Issue:** Out of memory
  - **Solution:** Use `yolov8n.pt` (nano) instead of larger models

### dbt Build Fails
- **Issue:** Table not found
  - **Solution:** Ensure `python scripts/load_raw_to_postgres.py` ran successfully
- **Issue:** Foreign key constraint
  - **Solution:** Check `dbt test` output; may indicate missing dimension records

### API Returns 500 Error
- **Issue:** Database connection failed
  - **Solution:** Verify PostgreSQL is running and DATABASE_URL is correct
- **Issue:** Table doesn't exist
  - **Solution:** Run `dbt build` to materialize marts

### Dagster Job Fails
- **Issue:** Op timeout
  - **Solution:** Increase timeout in op config or check logs for actual error
- **Issue:** Shell command not found
  - **Solution:** Ensure Python scripts are executable and in PATH

---

## Performance Considerations

- **YOLO inference:** ~50-100 ms per image on CPU; use GPU for large batches
- **dbt build:** ~30-60 seconds for full warehouse; use `--select` for incremental builds
- **API queries:** Indexed on `fct_messages(message_id, date_key, channel_key)` for fast lookups
- **Dagster:** Runs are logged to PostgreSQL; consider archiving old runs periodically

---

## Next Steps

1. **Fine-tune YOLO:** Label medical product images and fine-tune YOLOv8 for domain-specific detection
2. **Add dashboards:** Connect Metabase or Tableau to PostgreSQL for visual analytics
3. **Implement alerts:** Add Slack/email notifications for pipeline failures or data anomalies
4. **Scale infrastructure:** Move to cloud (AWS RDS, Airflow, SageMaker) for production workloads
5. **Add incremental models:** Use dbt incremental materializations for large fact tables

---

## Support

For issues or questions, refer to:
- dbt docs: https://docs.getdbt.com
- Dagster docs: https://docs.dagster.io
- FastAPI docs: https://fastapi.tiangolo.com
- YOLOv8 docs: https://docs.ultralytics.com
