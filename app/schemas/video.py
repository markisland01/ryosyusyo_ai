from datetime import datetime
from pydantic import BaseModel


class VideoResponse(BaseModel):
    id: int
    original_filename: str
    file_size: int
    status: str
    total_frames: int | None
    detected_receipts: int | None
    processed_frames: int | None
    ai_completed_requests: int | None
    ai_failed_requests: int | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class VideoStatusResponse(BaseModel):
    id: int
    status: str
    total_frames: int | None
    detected_receipts: int | None
    processed_frames: int | None
    ai_completed_requests: int | None
    ai_failed_requests: int | None
    error_message: str | None

    model_config = {"from_attributes": True}


class VideoListResponse(BaseModel):
    videos: list[VideoResponse]
    total: int
