from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.video import Video
from app.models.receipt import Receipt
from app.schemas.video import VideoListResponse

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("/", response_model=VideoListResponse)
async def get_history(
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Get processing history with pagination."""
    offset = (page - 1) * per_page

    count_result = await db.execute(select(func.count(Video.id)))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Video)
        .order_by(Video.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    videos = list(result.scalars().all())
    return VideoListResponse(videos=videos, total=total)
