"""
YOLO Object Detection for Telegram Images
Detects objects in images and classifies them into categories.
"""

import os
import glob
import json
import csv
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

import cv2
from ultralytics import YOLO
import psycopg2
from psycopg2.extras import execute_values


# Configuration
YOLO_MODEL = "yolov8n.pt"  # nano model for efficiency
IMAGE_BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "images")
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "yolo_detections.csv")
POSTGRES_DSN = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5432/medical_warehouse",
)

# YOLO class names (from COCO dataset)
YOLO_CLASSES = {
    0: "person",
    39: "bottle",
    41: "cup",
    42: "fork",
    43: "knife",
    44: "spoon",
    45: "bowl",
    47: "wine glass",
    48: "cup",
    50: "banana",
    51: "apple",
    52: "sandwich",
    53: "orange",
    54: "broccoli",
    55: "carrot",
    56: "hot dog",
    57: "pizza",
    58: "donut",
    59: "cake",
}


def classify_image(detections: List[Dict]) -> str:
    """
    Classify image based on detected objects.
    
    Categories:
    - promotional: person + bottle/container
    - product_display: bottle/container, no person
    - lifestyle: person, no product
    - other: neither
    """
    classes = [d["class_name"].lower() for d in detections]
    
    has_person = "person" in classes
    has_product = any(c in classes for c in ["bottle", "cup", "bowl", "wine glass"])
    
    if has_person and has_product:
        return "promotional"
    elif has_product and not has_person:
        return "product_display"
    elif has_person and not has_product:
        return "lifestyle"
    else:
        return "other"


def run_yolo_inference(image_path: str, model: YOLO) -> List[Dict]:
    """
    Run YOLO inference on a single image.
    Returns list of detections with class, confidence, and bbox.
    """
    try:
        results = model(image_path, verbose=False)
        detections = []
        
        for result in results:
            for box in result.boxes:
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                class_name = result.names.get(class_id, f"class_{class_id}")
                
                # Extract bbox coordinates
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                
                detections.append({
                    "class_id": class_id,
                    "class_name": class_name,
                    "confidence": round(confidence, 3),
                    "bbox": [round(x, 2) for x in [x1, y1, x2, y2]],
                })
        
        return detections
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return []


def extract_message_id_from_path(image_path: str) -> Optional[int]:
    """
    Extract message_id from image path.
    Expected format: data/raw/images/{channel_name}/{message_id}.jpg
    """
    try:
        filename = Path(image_path).stem
        return int(filename)
    except (ValueError, AttributeError):
        return None


def process_images(output_csv: str = OUTPUT_CSV) -> Tuple[int, int]:
    """
    Scan all images, run YOLO inference, and save results to CSV.
    Returns (total_processed, total_errors).
    """
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    
    # Load YOLO model
    print(f"Loading YOLO model: {YOLO_MODEL}")
    model = YOLO(YOLO_MODEL)
    
    # Collect all images
    image_paths = glob.glob(os.path.join(IMAGE_BASE_DIR, "**", "*.jpg"), recursive=True)
    print(f"Found {len(image_paths)} images to process")
    
    results = []
    errors = 0
    
    for idx, image_path in enumerate(image_paths, 1):
        if idx % 100 == 0:
            print(f"Processed {idx}/{len(image_paths)}")
        
        message_id = extract_message_id_from_path(image_path)
        if not message_id:
            errors += 1
            continue
        
        detections = run_yolo_inference(image_path, model)
        image_category = classify_image(detections)
        
        # Store top detection or mark as empty
        if detections:
            top_detection = max(detections, key=lambda x: x["confidence"])
            results.append({
                "message_id": message_id,
                "image_path": image_path,
                "detected_class": top_detection["class_name"],
                "confidence_score": top_detection["confidence"],
                "image_category": image_category,
                "all_detections": json.dumps(detections),
                "processed_at": datetime.utcnow().isoformat(),
            })
        else:
            results.append({
                "message_id": message_id,
                "image_path": image_path,
                "detected_class": None,
                "confidence_score": None,
                "image_category": "other",
                "all_detections": json.dumps([]),
                "processed_at": datetime.utcnow().isoformat(),
            })
    
    # Write to CSV
    if results:
        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        print(f"Saved {len(results)} detection results to {output_csv}")
    
    return len(results), errors


def load_detections_to_postgres(csv_path: str = OUTPUT_CSV):
    """
    Load YOLO detection results from CSV into PostgreSQL.
    Creates raw.cv_detections table if it doesn't exist.
    """
    if not os.path.exists(csv_path):
        print(f"CSV file not found: {csv_path}")
        return
    
    conn = psycopg2.connect(POSTGRES_DSN)
    try:
        with conn.cursor() as cur:
            # Create schema and table
            cur.execute("CREATE SCHEMA IF NOT EXISTS raw")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS raw.cv_detections (
                    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    message_id BIGINT NOT NULL,
                    image_path TEXT,
                    detected_class TEXT,
                    confidence_score NUMERIC,
                    image_category TEXT,
                    all_detections JSONB,
                    processed_at TIMESTAMP WITH TIME ZONE,
                    load_ts TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Read CSV and insert
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            if rows:
                cols = ["message_id", "image_path", "detected_class", "confidence_score", 
                        "image_category", "all_detections", "processed_at"]
                values = [
                    [
                        int(r["message_id"]),
                        r["image_path"],
                        r["detected_class"] if r["detected_class"] != "None" else None,
                        float(r["confidence_score"]) if r["confidence_score"] != "None" else None,
                        r["image_category"],
                        r["all_detections"],
                        r["processed_at"],
                    ]
                    for r in rows
                ]
                
                execute_values(
                    cur,
                    f"INSERT INTO raw.cv_detections ({','.join(cols)}) VALUES %s",
                    values,
                )
                print(f"Loaded {len(rows)} detection records into raw.cv_detections")
        
        conn.commit()
    finally:
        conn.close()


def main():
    print("Starting YOLO object detection pipeline...")
    processed, errors = process_images()
    print(f"Detection complete: {processed} processed, {errors} errors")
    
    print("Loading detections into PostgreSQL...")
    load_detections_to_postgres()
    print("Done!")


if __name__ == "__main__":
    main()
