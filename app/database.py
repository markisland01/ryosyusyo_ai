from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session


async def _migrate_receipts_table() -> None:
    async with engine.begin() as conn:
        result = await conn.execute(text("PRAGMA table_info(receipts)"))
        existing_columns = {row[1] for row in result.fetchall()}

        migrations = {
            "document_type": "ALTER TABLE receipts ADD COLUMN document_type VARCHAR(32)",
            "balance_amount": "ALTER TABLE receipts ADD COLUMN balance_amount INTEGER",
            "debit_amount": "ALTER TABLE receipts ADD COLUMN debit_amount INTEGER",
            "credit_amount": "ALTER TABLE receipts ADD COLUMN credit_amount INTEGER",
            "scene_start_frame": "ALTER TABLE receipts ADD COLUMN scene_start_frame INTEGER",
        }

        for column_name, sql in migrations.items():
            if column_name not in existing_columns:
                await conn.execute(text(sql))


async def _migrate_videos_table() -> None:
    async with engine.begin() as conn:
        result = await conn.execute(text("PRAGMA table_info(videos)"))
        existing_columns = {row[1] for row in result.fetchall()}

        migrations = {
            "processed_frames": "ALTER TABLE videos ADD COLUMN processed_frames INTEGER",
            "ai_completed_requests": "ALTER TABLE videos ADD COLUMN ai_completed_requests INTEGER",
            "ai_failed_requests": "ALTER TABLE videos ADD COLUMN ai_failed_requests INTEGER",
        }

        for column_name, sql in migrations.items():
            if column_name not in existing_columns:
                await conn.execute(text(sql))


async def _migrate_receipt_segments_table() -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS receipt_segments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    receipt_id INTEGER NOT NULL,
                    image_path VARCHAR(500) NOT NULL,
                    frame_number INTEGER,
                    segment_index INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME,
                    FOREIGN KEY(receipt_id) REFERENCES receipts(id)
                )
                """
            )
        )


async def _seed_default_rules() -> None:
    default_rules = [
        ("account_category", "receipt", "駐車場", "旅費交通費", 10, "駐車場は旅費交通費に寄せる"),
        ("account_category", "receipt", "タクシー", "旅費交通費", 11, "タクシーは旅費交通費に寄せる"),
        ("account_category", "receipt", "近鉄", "旅費交通費", 12, "鉄道系は旅費交通費に寄せる"),
        ("account_category", "receipt", "JR", "旅費交通費", 13, "鉄道系は旅費交通費に寄せる"),
        ("account_category", "receipt", "ガソリン", "旅費交通費", 14, "移動費は旅費交通費に寄せる"),
        ("account_category", "receipt", "レストラン", "会議費", 20, "飲食店は会議費に寄せる"),
        ("account_category", "receipt", "カフェ", "会議費", 21, "飲食店は会議費に寄せる"),
        ("account_category", "receipt", "Amazon", "消耗品費", 30, "EC購入は消耗品費に寄せる"),
        ("account_category", "receipt", "ドラッグ", "消耗品費", 31, "日用品購入は消耗品費に寄せる"),
        ("payment_method", "credit_statement", "visa", "クレジットカード", 10, "カード明細はクレジットカード"),
        ("payment_method", "credit_statement", "mastercard", "クレジットカード", 11, "カード明細はクレジットカード"),
        ("payment_method", "bankbook", "振込", "振込", 10, "通帳の振込を振込に寄せる"),
        ("payment_method", "bankbook", "ATM", "ATM", 11, "通帳のATMをATMに寄せる"),
        ("payment_method", "bankbook", "引落", "口座引落", 12, "通帳の引落を口座引落に寄せる"),
        ("invoice_type", "credit_statement", "card", "対象外", 10, "カード明細は請求区分対象外"),
        ("invoice_type", "bankbook", "普通預金", "対象外", 11, "通帳は請求区分対象外"),
    ]

    async with engine.begin() as conn:
        for rule_type, document_type, pattern, target_value, priority, notes in default_rules:
            existing = await conn.execute(
                text(
                    """
                    SELECT id
                    FROM rules
                    WHERE rule_type = :rule_type
                      AND COALESCE(document_type, '') = COALESCE(:document_type, '')
                      AND pattern = :pattern
                      AND target_value = :target_value
                    LIMIT 1
                    """
                ),
                {
                    "rule_type": rule_type,
                    "document_type": document_type,
                    "pattern": pattern,
                    "target_value": target_value,
                },
            )
            if existing.fetchone():
                continue

            await conn.execute(
                text(
                    """
                    INSERT INTO rules (
                        rule_type, document_type, pattern, target_value, priority, enabled, notes, created_at, updated_at
                    ) VALUES (
                        :rule_type, :document_type, :pattern, :target_value, :priority, 1, :notes, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "rule_type": rule_type,
                    "document_type": document_type,
                    "pattern": pattern,
                    "target_value": target_value,
                    "priority": priority,
                    "notes": notes,
                },
            )


async def init_db():
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _migrate_receipts_table()
    await _migrate_videos_table()
    await _migrate_receipt_segments_table()
    await _seed_default_rules()
