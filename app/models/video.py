import enum
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class VideoStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    EXTRACTING_FRAMES = "extracting_frames"
    DETECTING_RECEIPTS = "detecting_receipts"
    OCR_PROCESSING = "ocr_processing"
    AI_WAITING = "ai_waiting"
    AI_ANALYZING = "ai_analyzing"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    file_size: Mapped[int] = mapped_column(Integer)
    status: Mapped[VideoStatus] = mapped_column(
        Enum(VideoStatus), default=VideoStatus.UPLOADED
    )
    total_frames: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detected_receipts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_frames: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_completed_requests: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_failed_requests: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    receipts = relationship("Receipt", back_populates="video", cascade="all, delete-orphan")
