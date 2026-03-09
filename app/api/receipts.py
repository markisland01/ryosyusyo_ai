from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.receipt import Receipt
from app.schemas.receipt import ReceiptConfirmRequest, ReceiptResponse, ReceiptUpdate

router = APIRouter(prefix="/api/receipts", tags=["receipts"])


def _serialize_receipt(receipt: Receipt) -> dict:
    return {
        "id": receipt.id,
        "video_id": receipt.video_id,
        "image_path": receipt.image_path,
        "segment_image_paths": [segment.image_path for segment in receipt.segments] or [receipt.image_path],
        "scene_start_frame": receipt.scene_start_frame,
        "document_type": receipt.document_type.value if receipt.document_type else None,
        "receipt_date": receipt.receipt_date,
        "store_name": receipt.store_name,
        "total_amount": receipt.total_amount,
        "tax_excluded_amount": receipt.tax_excluded_amount,
        "tax_amount": receipt.tax_amount,
        "tax_8_amount": receipt.tax_8_amount,
        "tax_10_amount": receipt.tax_10_amount,
        "balance_amount": receipt.balance_amount,
        "debit_amount": receipt.debit_amount,
        "credit_amount": receipt.credit_amount,
        "payment_method": receipt.payment_method,
        "registration_number": receipt.registration_number,
        "invoice_type": receipt.invoice_type.value if receipt.invoice_type else None,
        "account_category": receipt.account_category,
        "description": receipt.description,
        "confidence_score": receipt.confidence_score,
        "is_confirmed": receipt.is_confirmed,
        "created_at": receipt.created_at,
    }


@router.get("/{receipt_id}", response_model=ReceiptResponse)
async def get_receipt(receipt_id: int, db: AsyncSession = Depends(get_db)):
    receipt = await db.get(Receipt, receipt_id, options=[selectinload(Receipt.segments)])
    if not receipt:
        raise HTTPException(status_code=404, detail="領収書が見つかりません")
    return _serialize_receipt(receipt)


@router.put("/{receipt_id}", response_model=ReceiptResponse)
async def update_receipt(receipt_id: int, data: ReceiptUpdate, db: AsyncSession = Depends(get_db)):
    receipt = await db.get(Receipt, receipt_id, options=[selectinload(Receipt.segments)])
    if not receipt:
        raise HTTPException(status_code=404, detail="領収書が見つかりません")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(receipt, field, value)

    await db.commit()
    await db.refresh(receipt)
    receipt = await db.get(Receipt, receipt_id, options=[selectinload(Receipt.segments)])
    return _serialize_receipt(receipt)


@router.post("/confirm")
async def confirm_receipts(request: ReceiptConfirmRequest, db: AsyncSession = Depends(get_db)):
    confirmed_count = 0
    for receipt_id in request.receipt_ids:
        receipt = await db.get(Receipt, receipt_id)
        if receipt:
            receipt.is_confirmed = True
            confirmed_count += 1

    await db.commit()
    return {"confirmed": confirmed_count}
