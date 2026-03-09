import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.receipt import Receipt
from app.services.csv_exporter import EXPORTERS

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/csv")
async def export_csv(
    video_id: int = Query(...),
    format: str = Query("generic", pattern="^(generic|yayoi|freee|moneyforward)$"),
    encoding: str = Query("utf-8-sig", pattern="^(utf-8-sig|shift_jis)$"),
    db: AsyncSession = Depends(get_db),
):
    """Export confirmed receipts as CSV."""
    result = await db.execute(
        select(Receipt)
        .where(Receipt.video_id == video_id, Receipt.is_confirmed == True)
        .order_by(Receipt.receipt_date, Receipt.id)
    )
    receipts = list(result.scalars().all())

    if not receipts:
        raise HTTPException(status_code=404, detail="確定済みの領収書がありません")

    exporter = EXPORTERS.get(format)
    if not exporter:
        raise HTTPException(status_code=400, detail="対応していない出力形式です")

    csv_content = exporter(receipts, encoding)
    csv_bytes = csv_content.encode(encoding)

    filename = f"receipts_{format}_{video_id}.csv"

    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
