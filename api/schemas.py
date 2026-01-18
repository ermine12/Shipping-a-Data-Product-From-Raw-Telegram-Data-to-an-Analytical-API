from pydantic import BaseModel

from typing import Optional

class HealthResponse(BaseModel):

    status: str

class MessageResponse(BaseModel):

    message: str

# Add more schemas as needed for medical data, e.g.

class MedicalData(BaseModel):

    id: int

    content: str

    timestamp: str

    # etc.