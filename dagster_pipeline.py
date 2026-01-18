"""
Dagster pipeline for end-to-end data orchestration.
Orchestrates scraping, ingestion, enrichment, transformations, and tests.
"""

import os
import subprocess
from datetime import datetime
from typing import Optional

from dagster import (
    job,
    op,
    Out,
    In,
    DynamicOut,
    DynamicOutput,
    graph,
    Field,
    String,
    Int,
    resource,
    io_manager,
    IOManager,
    DagsterInvariantViolationError,
)
from dagster_shell import execute_shell_command


# ============================================================================
# Resources
# ============================================================================

@resource
def postgres_resource(context):
    """PostgreSQL connection resource."""
    return {
        "dsn": os.getenv(
            "DATABASE_URL",
            "postgresql://user:password@localhost:5432/medical_warehouse",
        ),
    }


@resource
def dbt_resource(context):
    """dbt project resource."""
    return {
        "project_dir": os.path.join(
            os.path.dirname(__file__), "..", "medical_warehouse"
        ),
    }


# ============================================================================
# Ops
# ============================================================================

@op(
    config_schema={
        "channels": Field(
            String,
            default_value="",
            description="Comma-separated list of channels to scrape (empty = all)",
        ),
        "limit": Field(
            Int,
            default_value=100,
            description="Max messages per channel",
        ),
    },
    tags={"team": "data-ingestion"},
)
def op_scrape_telegram_data(context) -> dict:
    """
    Scrape Telegram channels and save JSON/images to data lake.
    Runs scripts/telegram.py.
    """
    context.log.info("Starting Telegram scrape...")
    
    channels = context.op_config.get("channels", "")
    limit = context.op_config.get("limit", 100)
    
    cmd = f"python scripts/telegram.py"
    if channels:
        cmd += f" --channels {channels}"
    if limit:
        cmd += f" --limit {limit}"
    
    try:
        result = execute_shell_command(cmd, output_logging="INGEST")
        context.log.info(f"Scrape completed: {result}")
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "command": cmd,
        }
    except Exception as e:
        context.log.error(f"Scrape failed: {e}")
        raise


@op(
    ins={"scrape_result": In(dict)},
    tags={"team": "data-ingestion"},
)
def op_load_raw_to_postgres(context, scrape_result: dict) -> dict:
    """
    Load raw JSON from data lake into PostgreSQL raw schema.
    Runs scripts/load_raw_to_postgres.py.
    """
    context.log.info("Loading raw data to PostgreSQL...")
    
    try:
        result = execute_shell_command(
            "python scripts/load_raw_to_postgres.py",
            output_logging="INGEST",
        )
        context.log.info(f"Load completed: {result}")
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "depends_on": scrape_result,
        }
    except Exception as e:
        context.log.error(f"Load failed: {e}")
        raise


@op(
    ins={"load_result": In(dict)},
    tags={"team": "enrichment"},
)
def op_yolo_enrichment(context, load_result: dict) -> dict:
    """
    Run YOLO object detection on images and load results to PostgreSQL.
    Runs src/yolo_detect.py.
    """
    context.log.info("Starting YOLO enrichment...")
    
    try:
        result = execute_shell_command(
            "python src/yolo_detect.py",
            output_logging="INGEST",
        )
        context.log.info(f"YOLO enrichment completed: {result}")
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "depends_on": load_result,
        }
    except Exception as e:
        context.log.error(f"YOLO enrichment failed: {e}")
        raise


@op(
    ins={"yolo_result": In(dict)},
    config_schema={
        "select": Field(
            String,
            default_value="",
            description="dbt --select filter (e.g., 'staging' or 'marts')",
        ),
    },
    tags={"team": "transformation"},
)
def op_dbt_build(context, yolo_result: dict) -> dict:
    """
    Run dbt build to execute models and tests.
    """
    context.log.info("Starting dbt build...")
    
    dbt_dir = os.path.join(
        os.path.dirname(__file__), "..", "medical_warehouse"
    )
    select_filter = context.op_config.get("select", "")
    
    cmd = f"cd {dbt_dir} && dbt build"
    if select_filter:
        cmd += f" --select {select_filter}"
    
    try:
        result = execute_shell_command(cmd, output_logging="INGEST")
        context.log.info(f"dbt build completed: {result}")
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "depends_on": yolo_result,
        }
    except Exception as e:
        context.log.error(f"dbt build failed: {e}")
        raise


@op(
    ins={"build_result": In(dict)},
    tags={"team": "transformation"},
)
def op_dbt_test(context, build_result: dict) -> dict:
    """
    Run dbt test to validate data quality.
    Fails if any tests fail.
    """
    context.log.info("Running dbt tests...")
    
    dbt_dir = os.path.join(
        os.path.dirname(__file__), "..", "medical_warehouse"
    )
    
    cmd = f"cd {dbt_dir} && dbt test"
    
    try:
        result = execute_shell_command(cmd, output_logging="INGEST")
        context.log.info(f"dbt tests passed: {result}")
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "depends_on": build_result,
        }
    except Exception as e:
        context.log.error(f"dbt tests failed: {e}")
        raise


@op(
    ins={"test_result": In(dict)},
    tags={"team": "documentation"},
)
def op_dbt_docs(context, test_result: dict) -> dict:
    """
    Generate dbt documentation.
    """
    context.log.info("Generating dbt documentation...")
    
    dbt_dir = os.path.join(
        os.path.dirname(__file__), "..", "medical_warehouse"
    )
    
    cmd = f"cd {dbt_dir} && dbt docs generate"
    
    try:
        result = execute_shell_command(cmd, output_logging="INGEST")
        context.log.info(f"dbt docs generated: {result}")
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "docs_path": os.path.join(dbt_dir, "target", "index.html"),
            "depends_on": test_result,
        }
    except Exception as e:
        context.log.error(f"dbt docs generation failed: {e}")
        raise


@op(
    ins={"docs_result": In(dict)},
    tags={"team": "api"},
)
def op_api_health_check(context, docs_result: dict) -> dict:
    """
    Verify API is running and responsive.
    """
    context.log.info("Running API health check...")
    
    try:
        import requests
        
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            context.log.info("API health check passed")
            return {
                "status": "success",
                "timestamp": datetime.utcnow().isoformat(),
                "api_status": response.json(),
                "depends_on": docs_result,
            }
        else:
            raise Exception(f"API returned status {response.status_code}")
    except Exception as e:
        context.log.warning(f"API health check failed (non-critical): {e}")
        return {
            "status": "warning",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
            "depends_on": docs_result,
        }


# ============================================================================
# Jobs
# ============================================================================

@job(
    name="daily_ingestion_job",
    description="Daily pipeline: scrape -> load -> enrich -> transform -> test -> docs -> health",
    tags={"owner": "data-team", "frequency": "daily"},
)
def daily_ingestion_job():
    """
    End-to-end daily pipeline.
    """
    scrape_result = op_scrape_telegram_data()
    load_result = op_load_raw_to_postgres(scrape_result)
    yolo_result = op_yolo_enrichment(load_result)
    build_result = op_dbt_build(yolo_result)
    test_result = op_dbt_test(build_result)
    docs_result = op_dbt_docs(test_result)
    op_api_health_check(docs_result)


@job(
    name="backfill_job",
    description="Backfill pipeline for historical reprocessing",
    tags={"owner": "data-team", "frequency": "manual"},
)
def backfill_job():
    """
    Backfill pipeline (skip scraping, start from raw load).
    """
    load_result = op_load_raw_to_postgres({"status": "backfill_start"})
    yolo_result = op_yolo_enrichment(load_result)
    build_result = op_dbt_build(yolo_result)
    test_result = op_dbt_test(build_result)
    docs_result = op_dbt_docs(test_result)
    op_api_health_check(docs_result)


@job(
    name="transform_only_job",
    description="Transform-only pipeline (skip scraping and enrichment)",
    tags={"owner": "data-team", "frequency": "manual"},
)
def transform_only_job():
    """
    Transform-only pipeline for quick iteration.
    """
    build_result = op_dbt_build({"status": "transform_start"})
    test_result = op_dbt_test(build_result)
    docs_result = op_dbt_docs(test_result)
    op_api_health_check(docs_result)


# ============================================================================
# Schedules (optional, requires Dagster daemon)
# ============================================================================

from dagster import schedule, DefaultSensorDefinition
from dagster._core.definitions.schedule_definition import ScheduleDefinition

# Example: daily schedule at 2 AM UTC
# daily_schedule = schedule(
#     job=daily_ingestion_job,
#     cron_schedule="0 2 * * *",
#     description="Daily ingestion at 2 AM UTC",
# )
