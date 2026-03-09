import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _resolve_storage_path(value: str, default: Path) -> Path:
    raw = Path(value) if value else default
    if not raw.is_absolute():
        raw = (BASE_DIR / raw).resolve()
    return raw

# Database
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR / 'ryosyusyo.db'}")

# Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
AI_MAX_CONCURRENCY = int(os.getenv("AI_MAX_CONCURRENCY", "2"))
AI_REQUEST_TIMEOUT_SECONDS = int(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "45"))
AI_MAX_RETRIES = int(os.getenv("AI_MAX_RETRIES", "3"))
AI_RETRY_BASE_SECONDS = float(os.getenv("AI_RETRY_BASE_SECONDS", "2"))

# File paths
UPLOAD_DIR = _resolve_storage_path(os.getenv("UPLOAD_DIR", ""), BASE_DIR / "uploads")
OUTPUT_DIR = _resolve_storage_path(os.getenv("OUTPUT_DIR", ""), BASE_DIR / "outputs")
LOG_DIR = _resolve_storage_path(os.getenv("LOG_DIR", ""), BASE_DIR / "logs")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Upload limits
MAX_VIDEO_SIZE_MB = int(os.getenv("MAX_VIDEO_SIZE_MB", "500"))
MAX_VIDEO_SIZE_BYTES = MAX_VIDEO_SIZE_MB * 1024 * 1024
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".webm"}

# OCR
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "tesseract")

# Video processing
FRAME_SAMPLE_FPS = 2  # Extract 2 frames per second
MIN_RECEIPT_AREA_RATIO = 0.05  # Minimum receipt area as ratio of frame
BLUR_THRESHOLD = 100  # Laplacian variance threshold for blur detection
