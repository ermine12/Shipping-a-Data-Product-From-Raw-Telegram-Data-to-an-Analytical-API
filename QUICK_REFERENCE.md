# Quick Reference Guide

## Project Overview

**Medical Telegram Data Warehouse** - A complete data product that transforms raw Telegram channel data into actionable market intelligence for Ethiopian medical businesses.

**Status:** Tasks 1-5 Complete ✓

---

## Quick Start (5 minutes)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start database
docker-compose up -d db

# 3. Initialize warehouse
cd medical_warehouse && dbt deps && dbt build && cd ..

# 4. Run pipeline (Dagster)
dagster dev -f dagster_pipeline.py
# Open http://localhost:3000

# 5. Query API
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
# Open http://localhost:8000/docs
```

---

## File Structure

```
├── api/                          # FastAPI application
│   ├── main.py                   # 8 analytical endpoints
│   ├── schemas.py                # Pydantic models
│   └── database.py               # SQLAlchemy setup
├── data/
│   ├── raw/
│   │   ├── telegram_messages/    # JSON by date (Task 1)
│   │   ├── images/               # Downloaded images (Task 1)
���   │   └── csv/                  # CSV exports (Task 1)
│   └── processed/
│       └── yolo_detections.csv   # YOLO results (Task 3)
├── medical_warehouse/            # dbt project (Task 2)
│   ├── models/
│   │   ├── staging/
│   │   │   └── stg_telegram_messages.sql
│   │   └── marts/
│   │       ├── dim_dates.sql
│   │       ├── dim_channels.sql
│   │       ├── fct_messages.sql
│   │       ├── fct_image_detections.sql
│   │       └── schema.yml
│   ├── tests/
│   │   ├── assert_no_future_messages.sql
│   │   └── assert_valid_confidence_scores.sql
│   ├── dbt_project.yml
│   └── profiles.yml
├── scripts/
│   ├── telegram.py               # Telethon scraper (Task 1)
│   └── load_raw_to_postgres.py   # Raw data loader (Task 2)
├── src/
│   └── yolo_detect.py            # YOLO inference (Task 3)
├── dagster_pipeline.py           # Orchestration (Task 5)
├── docker-compose.yml            # Services
├── requirements.txt              # Dependencies
├── PROJECT_REPORT.md             # Full report
├── IMPLEMENTATION_GUIDE.md       # Detailed runbook
└── STAR_SCHEMA_DIAGRAM.md        # ER diagrams
```

---

## Task Breakdown

### Task 1: Telegram Scraping ✓
**File:** `scripts/telegram.py`
**Tool:** Telethon
**Output:** JSON + images in data lake

```bash
python scripts/telegram.py --channels "channel1,channel2" --limit 100
```

### Task 2: Data Warehouse ✓
**Files:** `medical_warehouse/` + `scripts/load_raw_to_postgres.py`
**Tool:** PostgreSQL + dbt
**Output:** Star schema with tests

```bash
python scripts/load_raw_to_postgres.py
cd medical_warehouse && dbt build && dbt test
```

### Task 3: YOLO Enrichment ✓
**File:** `src/yolo_detect.py`
**Tool:** YOLOv8 nano
**Output:** Image classifications + detections

```bash
python src/yolo_detect.py
```

### Task 4: Analytical API ✓
**Files:** `api/main.py` + `api/schemas.py`
**Tool:** FastAPI
**Output:** 8 REST endpoints

```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### Task 5: Orchestration ✓
**File:** `dagster_pipeline.py`
**Tool:** Dagster
**Output:** Automated daily pipeline

```bash
dagster dev -f dagster_pipeline.py
```

---

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Database health check |
| `/api/reports/top-products` | GET | Most mentioned terms |
| `/api/channels/{channel_name}/activity` | GET | Channel stats |
| `/api/search/messages` | GET | Full-text search |
| `/api/reports/visual-content` | GET | Image usage stats |
| `/api/reports/image-detections` | GET | YOLO results |
| `/api/channels` | GET | All channels |
| `/api/reports/top-messages` | GET | Top posts by engagement |

**Example:**
```bash
curl "http://localhost:8000/api/reports/top-products?limit=10"
curl "http://localhost:8000/api/channels/Medical%20Supplies/activity"
curl "http://localhost:8000/api/search/messages?query=paracetamol&limit=20"
```

---

## Database Schema

**Raw Zone:**
- `raw.telegram_messages` - Original scraped data
- `raw.cv_detections` - YOLO detection results

**Staging:**
- `stg_telegram_messages` - Cleaned messages (view)
- `stg_cv_detections` - Cleaned detections (view)

**Marts:**
- `dim_dates` - Calendar dimension
- `dim_channels` - Channel dimension
- `fct_messages` - Message facts
- `fct_image_detections` - Detection facts

---

## Dagster Jobs

| Job | Purpose | Trigger |
|-----|---------|---------|
| `daily_ingestion_job` | Full pipeline: scrape → load → enrich → transform → test → docs | Daily (2 AM UTC) |
| `backfill_job` | Reprocess without scraping | Manual |
| `transform_only_job` | Quick dbt iteration | Manual |

**Run in Dagster UI:**
1. Open http://localhost:3000
2. Click "Launchpad"
3. Select job
4. Configure options
5. Click "Launch Run"

---

## Data Quality Tests

**Generic tests (dbt):**
- `unique` on all primary keys
- `not_null` on critical columns
- `relationships` on foreign keys

**Custom tests:**
- `assert_no_future_messages.sql` - No messages with future dates
- `assert_valid_confidence_scores.sql` - Confidence scores 0-1

**Run tests:**
```bash
cd medical_warehouse && dbt test
```

---

## Performance Tips

**For large volumes:**
- Use incremental dbt models
- Add indexes on join keys
- Partition fact tables by date
- Use materialized views for common aggregations

**For YOLO:**
- Use GPU if available (10x faster)
- Batch process images (50-100 per batch)
- Use yolov8n (nano) for CPU

**For API:**
- Add Redis caching (TTL: 1 hour)
- Use connection pooling
- Add rate limiting

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: No module named 'ultralytics'` | `pip install ultralytics` |
| `psycopg2.OperationalError: could not connect to server` | Ensure PostgreSQL running: `docker-compose up -d db` |
| `dbt: command not found` | `pip install dbt-core dbt-postgres` |
| `dagster: command not found` | `pip install dagster dagster-webserver` |
| API returns 500 | Check logs: `docker-compose logs api` |
| dbt build fails | Run `dbt debug` to check connection |

---

## Key Metrics

**Data Volume:**
- Messages: ~5,000-10,000 per day (depends on channels)
- Images: ~1,000-2,000 per day
- Channels: 10-50 active channels

**Performance:**
- Scraping: ~5-10 minutes per 100 channels
- YOLO inference: ~50-100 ms per image
- dbt build: ~30-60 seconds
- API query: <100 ms (with indexes)

**Storage:**
- Raw JSON: ~100 MB per day
- Images: ~500 MB per day
- Warehouse: ~1 GB per month

---

## Business KPIs

| KPI | Query |
|-----|-------|
| Top products | `GET /api/reports/top-products` |
| Channel activity | `GET /api/channels/{name}/activity` |
| Engagement trends | `GET /api/reports/top-messages?days=30` |
| Image usage | `GET /api/reports/visual-content` |
| Detection results | `GET /api/reports/image-detections` |

---

## Documentation

- **Full Report:** `PROJECT_REPORT.md`
- **Implementation Guide:** `IMPLEMENTATION_GUIDE.md`
- **Star Schema:** `STAR_SCHEMA_DIAGRAM.md`
- **dbt Docs:** `cd medical_warehouse && dbt docs serve`
- **API Docs:** `http://localhost:8000/docs`

---

## Next Steps

1. **Fine-tune YOLO:** Label medical products, fine-tune model
2. **Add dashboards:** Connect Metabase/Tableau
3. **Scale infrastructure:** Move to AWS/GCP
4. **Implement alerts:** Slack/email notifications
5. **Add incremental models:** For large volumes

---

## Support

- **dbt:** https://docs.getdbt.com
- **Dagster:** https://docs.dagster.io
- **FastAPI:** https://fastapi.tiangolo.com
- **YOLOv8:** https://docs.ultralytics.com
- **Telethon:** https://docs.telethon.dev

---

**Last Updated:** 2025-01-18
**Status:** Production Ready
