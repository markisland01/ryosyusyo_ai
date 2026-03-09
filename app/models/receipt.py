import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InvoiceType(str, enum.Enum):
    QUALIFIED = "適格請求書"
    CATEGORIZED = "区分記載請求書"
    NOT_APPLICABLE = "対象外"


class DocumentType(str, enum.Enum):
    RECEIPT = "receipt"
    CREDIT_STATEMENT = "credit_statement"
    BANKBOOK = "bankbook"
    INVOICE = "invoice"
    OTHER = "other"


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"))
    image_path: Mapped[str] = mapped_column(String(500))
    scene_start_frame: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frame_number: Mapped[int] = mapped_column(Integer)

    document_type: Mapped[DocumentType | None] = mapped_column(Enum(DocumentType), nullable=True)
    receipt_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    store_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tax_excluded_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tax_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tax_8_amount: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="8%税額")
    tax_10_amount: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="10%税額")
    balance_amount: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="通帳などの残高")
    debit_amount: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="出金額")
    credit_amount: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="入金額")
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(
        String(14), nullable=True, comment="T+13桁の登録番号"
    )
    invoice_type: Mapped[InvoiceType | None] = mapped_column(Enum(InvoiceType), nullable=True)
    account_category: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="会計ソフト向け勘定科目"
    )
    description: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="摘要")
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    ocr_raw_text: Mapped[str | None] = mapped_column(String(5000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    video = relationship("Video", back_populates="receipts")
    segments = relationship(
        "ReceiptSegment",
        back_populates="receipt",
        cascade="all, delete-orphan",
        order_by="ReceiptSegment.segment_index",
    )


class ReceiptSegment(Base):
    __tablename__ = "receipt_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipts.id"))
    image_path: Mapped[str] = mapped_column(String(500))
    frame_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    segment_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    receipt = relationship("Receipt", back_populates="segments")
