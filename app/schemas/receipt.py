from datetime import date, datetime

from pydantic import BaseModel


class ReceiptResponse(BaseModel):
    id: int
    video_id: int
    image_path: str
    segment_image_paths: list[str] = []
    scene_start_frame: int | None
    document_type: str | None
    receipt_date: date | None
    store_name: str | None
    total_amount: int | None
    tax_excluded_amount: int | None
    tax_amount: int | None
    tax_8_amount: int | None
    tax_10_amount: int | None
    balance_amount: int | None
    debit_amount: int | None
    credit_amount: int | None
    payment_method: str | None
    registration_number: str | None
    invoice_type: str | None
    account_category: str | None
    description: str | None
    confidence_score: float | None
    is_confirmed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ReceiptUpdate(BaseModel):
    scene_start_frame: int | None = None
    document_type: str | None = None
    receipt_date: date | None = None
    store_name: str | None = None
    total_amount: int | None = None
    tax_excluded_amount: int | None = None
    tax_amount: int | None = None
    tax_8_amount: int | None = None
    tax_10_amount: int | None = None
    balance_amount: int | None = None
    debit_amount: int | None = None
    credit_amount: int | None = None
    payment_method: str | None = None
    registration_number: str | None = None
    invoice_type: str | None = None
    account_category: str | None = None
    description: str | None = None


class ReceiptListResponse(BaseModel):
    receipts: list[ReceiptResponse]
    total: int


class ReceiptConfirmRequest(BaseModel):
    receipt_ids: list[int]
