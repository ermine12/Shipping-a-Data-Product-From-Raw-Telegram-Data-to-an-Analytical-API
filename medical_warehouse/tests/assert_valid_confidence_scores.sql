-- Ensure confidence scores are between 0 and 1 when present
select 1
from {{ ref('fct_image_detections') }}
where confidence_score is not null
  and (confidence_score < 0 or confidence_score > 1)
limit 1;