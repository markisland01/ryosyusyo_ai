import asyncio
from datetime import datetime
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import (
    AI_MAX_CONCURRENCY,
    AI_MAX_RETRIES,
    AI_REQUEST_TIMEOUT_SECONDS,
    AI_RETRY_BASE_SECONDS,
    ALLOWED_VIDEO_EXTENSIONS,
    LOG_DIR,
    MAX_VIDEO_SIZE_BYTES,
    OUTPUT_DIR,
    UPLOAD_DIR,
)
from app.database import get_db
from app.models.receipt import Receipt, ReceiptSegment
from app.models.video import Video, VideoStatus
from app.schemas.receipt import ReceiptListResponse
from app.schemas.video import VideoListResponse, VideoResponse, VideoStatusResponse
from app.services.ai_extractor import extract_receipt_data
from app.services.document_normalizer import load_active_rules, normalize_document_fields
from app.services.ocr_service import extract_text
from app.services.video_processor import process_video

router = APIRouter(prefix="/api/videos", tags=["videos"])

_ai_semaphore = asyncio.Semaphore(max(1, AI_MAX_CONCURRENCY))


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


def _video_log_path(video_id: int) -> Path:
    return LOG_DIR / f"video_{video_id}.log"


def _append_video_log(video_id: int, message: str) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")
    with _video_log_path(video_id).open("a", encoding="utf-8") as fh:
        fh.write(f"[{timestamp}] {message}\n")


def _merge_ocr_texts(texts: list[str]) -> str:
    seen: set[str] = set()
    merged_lines: list[str] = []
    for text in texts:
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line in seen:
                continue
            seen.add(line)
            merged_lines.append(line)
    return "\n".join(merged_lines)


async def _persist_video_progress(
    db: AsyncSession,
    video: Video,
    *,
    status: VideoStatus | None = None,
    total_frames: int | None = None,
    processed_frames: int | None = None,
    ai_completed_requests: int | None = None,
    ai_failed_requests: int | None = None,
    detected_receipts: int | None = None,
    error_message: str | None = None,
) -> None:
    if status is not None:
        video.status = status
    if total_frames is not None:
        video.total_frames = total_frames
    if processed_frames is not None:
        video.processed_frames = processed_frames
    if ai_completed_requests is not None:
        video.ai_completed_requests = ai_completed_requests
    if ai_failed_requests is not None:
        video.ai_failed_requests = ai_failed_requests
    if detected_receipts is not None:
        video.detected_receipts = detected_receipts
    if error_message is not None:
        video.error_message = error_message
    await db.commit()


async def _extract_items_with_retry(video: Video, result: dict) -> tuple[str, list[dict]]:
    image_paths = result.get("segment_image_paths") or [result["image_path"]]
    ocr_texts: list[str] = []
    _append_video_log(video.id, f"start result frame={result['frame_number']} images={len(image_paths)}")

    for image_path in image_paths:
        try:
            segment_text = await asyncio.to_thread(extract_text, image_path)
            if segment_text.strip():
                ocr_texts.append(segment_text)
            _append_video_log(video.id, f"ocr ok frame={result['frame_number']} chars={len(segment_text)} image={image_path}")
        except Exception:
            _append_video_log(video.id, f"ocr skipped frame={result['frame_number']} image={image_path}")

    ocr_text = _merge_ocr_texts(ocr_texts)
    last_error: Exception | None = None
    for attempt in range(1, AI_MAX_RETRIES + 1):
        try:
            _append_video_log(video.id, f"ai request frame={result['frame_number']} attempt={attempt} images={len(image_paths)}")
            async with _ai_semaphore:
                items = await asyncio.wait_for(
                    asyncio.to_thread(extract_receipt_data, ocr_text, image_paths),
                    timeout=AI_REQUEST_TIMEOUT_SECONDS,
                )
            _append_video_log(video.id, f"ai success frame={result['frame_number']} attempt={attempt} items={len(items)}")
            return ocr_text, items
        except Exception as exc:
            last_error = exc
            _append_video_log(video.id, f"ai error frame={result['frame_number']} attempt={attempt} error={type(exc).__name__}: {exc}")
            if attempt >= AI_MAX_RETRIES:
                break
            video.status = VideoStatus.RETRYING
            await asyncio.sleep(AI_RETRY_BASE_SECONDS * attempt)

    raise RuntimeError(f"AI extraction failed for {image_paths}: {last_error}")


async def _process_single_result(video: Video, result: dict) -> tuple[str, list[dict]]:
    return await _extract_items_with_retry(video, result)


async def _process_single_result_with_context(video: Video, result: dict) -> tuple[dict, tuple[str, list[dict]]]:
    processed = await _process_single_result(video, result)
    return result, processed


async def _process_video_task(video_id: int, file_path: str, db_url: str):
    from app.database import async_session

    async with async_session() as db:
        video = await db.get(Video, video_id)
        if not video:
            return

        try:
            _append_video_log(video.id, f"task start file={file_path}")
            await _persist_video_progress(
                db,
                video,
                status=VideoStatus.EXTRACTING_FRAMES,
                processed_frames=0,
                ai_completed_requests=0,
                ai_failed_requests=0,
                detected_receipts=0,
                error_message=None,
            )

            results = await asyncio.to_thread(process_video, file_path, video_id)
            _append_video_log(video.id, f"frame extraction complete candidates={len(results)}")

            await _persist_video_progress(
                db,
                video,
                status=VideoStatus.AI_WAITING,
                total_frames=len(results),
                processed_frames=0,
                ai_completed_requests=0,
                ai_failed_requests=0,
            )

            tasks = [asyncio.create_task(_process_single_result_with_context(video, result)) for result in results]
            active_rules = await load_active_rules(db)
            await _persist_video_progress(db, video, status=VideoStatus.AI_ANALYZING)

            actual_items = 0
            completed_requests = 0
            failed_requests = 0
            first_error = None

            for task in asyncio.as_completed(tasks):
                try:
                    result, processed_item = await task
                except Exception as exc:
                    processed_item = exc
                    result = {"frame_number": -1, "image_path": "unknown", "segment_image_paths": ["unknown"]}

                if isinstance(processed_item, Exception):
                    failed_requests += 1
                    _append_video_log(video.id, f"result failed frame={result['frame_number']} processed={completed_requests + failed_requests}/{len(results)}")
                    if first_error is None:
                        first_error = processed_item
                    await _persist_video_progress(
                        db,
                        video,
                        status=VideoStatus.RETRYING if failed_requests < len(results) else video.status,
                        processed_frames=completed_requests + failed_requests,
                        ai_completed_requests=completed_requests,
                        ai_failed_requests=failed_requests,
                    )
                    continue

                completed_requests += 1
                ocr_text, extracted_items = processed_item
                _append_video_log(video.id, f"result completed frame={result['frame_number']} processed={completed_requests + failed_requests}/{len(results)} extracted_items={len(extracted_items)}")

                for extracted in extracted_items:
                    extracted["ocr_raw_text"] = ocr_text if ocr_text else None
                    extracted = normalize_document_fields(extracted, active_rules)
                    actual_items += 1

                    amount = extracted.get("total_amount")
                    debit_amount = extracted.get("debit_amount")
                    credit_amount = extracted.get("credit_amount")
                    if amount is not None:
                        if amount < 0 and debit_amount is None:
                            debit_amount = abs(amount)
                        elif amount > 0 and credit_amount is None and extracted.get("document_type") == "bankbook":
                            credit_amount = amount

                    receipt = Receipt(
                        video_id=video_id,
                        image_path=result["image_path"],
                        scene_start_frame=result.get("scene_start_frame"),
                        frame_number=result["frame_number"],
                        document_type=extracted.get("document_type"),
                        receipt_date=extracted.get("receipt_date"),
                        store_name=extracted.get("store_name"),
                        total_amount=amount,
                        tax_excluded_amount=extracted.get("tax_excluded_amount"),
                        tax_amount=extracted.get("tax_amount"),
                        tax_8_amount=extracted.get("tax_8_amount"),
                        tax_10_amount=extracted.get("tax_10_amount"),
                        balance_amount=extracted.get("balance_amount"),
                        debit_amount=debit_amount,
                        credit_amount=credit_amount,
                        payment_method=extracted.get("payment_method"),
                        registration_number=extracted.get("registration_number"),
                        invoice_type=extracted.get("invoice_type"),
                        account_category=extracted.get("account_category"),
                        description=extracted.get("description"),
                        confidence_score=extracted.get("confidence_score"),
                        ocr_raw_text=ocr_text if ocr_text else None,
                    )
                    db.add(receipt)
                    await db.flush()

                    segment_paths = result.get("segment_image_paths") or [result["image_path"]]
                    segment_frames = result.get("segment_frame_numbers") or [result["frame_number"]]
                    for segment_index, image_path in enumerate(segment_paths):
                        db.add(
                            ReceiptSegment(
                                receipt_id=receipt.id,
                                image_path=image_path,
                                frame_number=segment_frames[min(segment_index, len(segment_frames) - 1)],
                                segment_index=segment_index,
                            )
                        )

                await _persist_video_progress(
                    db,
                    video,
                    status=VideoStatus.AI_ANALYZING,
                    processed_frames=completed_requests + failed_requests,
                    ai_completed_requests=completed_requests,
                    ai_failed_requests=failed_requests,
                    detected_receipts=actual_items,
                )

            final_status = VideoStatus.COMPLETED
            final_error = None
            if first_error and actual_items == 0:
                final_status = VideoStatus.FAILED
                final_error = str(first_error)[:1000]

            _append_video_log(video.id, f"task finished status={final_status.value} completed={completed_requests} failed={failed_requests} detected={actual_items}")
            await _persist_video_progress(
                db,
                video,
                status=final_status,
                processed_frames=completed_requests + failed_requests,
                ai_completed_requests=completed_requests,
                ai_failed_requests=failed_requests,
                detected_receipts=actual_items,
                error_message=final_error,
            )

        except Exception as exc:
            try:
                await db.rollback()
            except Exception:
                pass
            _append_video_log(video_id, f"task crashed error={type(exc).__name__}: {exc}")
            await _persist_video_progress(db, video, status=VideoStatus.FAILED, error_message=str(exc)[:1000])


async def _ensure_capacity(db: AsyncSession) -> None:
    result = await db.execute(
        select(Video).where(Video.status.in_([VideoStatus.AI_WAITING, VideoStatus.AI_ANALYZING, VideoStatus.RETRYING]))
    )
    active_videos = list(result.scalars().all())
    if len(active_videos) >= AI_MAX_CONCURRENCY * 3:
        raise HTTPException(status_code=429, detail="現在処理が混み合っています。少し待ってから再試行してください")


@router.post("/upload", response_model=VideoResponse)
async def upload_video(background_tasks: BackgroundTasks, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"対応していないファイル形式です。対応形式: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}")

    content = await file.read()
    if len(content) > MAX_VIDEO_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="ファイルサイズが上限を超えています")

    await _ensure_capacity(db)

    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = UPLOAD_DIR / unique_name
    file_path.write_bytes(content)

    new_video = Video(
        filename=unique_name,
        original_filename=file.filename or "unknown",
        file_path=str(file_path),
        file_size=len(content),
        status=VideoStatus.UPLOADED,
        total_frames=0,
        processed_frames=0,
        ai_completed_requests=0,
        ai_failed_requests=0,
        detected_receipts=0,
    )
    db.add(new_video)
    await db.commit()
    await db.refresh(new_video)

    background_tasks.add_task(_process_video_task, new_video.id, str(file_path), "")
    return new_video


@router.post("/{video_id}/reprocess", response_model=VideoResponse)
async def reprocess_video(video_id: int, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    video = await db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="動画が見つかりません")

    if video.status in {VideoStatus.AI_WAITING, VideoStatus.AI_ANALYZING, VideoStatus.RETRYING, VideoStatus.EXTRACTING_FRAMES}:
        raise HTTPException(status_code=409, detail="この動画は現在処理中です")

    await _ensure_capacity(db)

    await db.execute(delete(ReceiptSegment).where(ReceiptSegment.receipt_id.in_(select(Receipt.id).where(Receipt.video_id == video_id))))
    await db.execute(delete(Receipt).where(Receipt.video_id == video_id))
    output_dir = OUTPUT_DIR / str(video_id)
    if output_dir.exists():
        shutil.rmtree(output_dir)

    video.status = VideoStatus.UPLOADED
    video.total_frames = 0
    video.processed_frames = 0
    video.ai_completed_requests = 0
    video.ai_failed_requests = 0
    video.detected_receipts = 0
    video.error_message = None
    await db.commit()
    await db.refresh(video)

    background_tasks.add_task(_process_video_task, video.id, video.file_path, "")
    return video


@router.get("/{video_id}/status", response_model=VideoStatusResponse)
async def get_video_status(video_id: int, db: AsyncSession = Depends(get_db)):
    video = await db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="動画が見つかりません")
    return video


@router.get("/{video_id}/receipts", response_model=ReceiptListResponse)
async def get_video_receipts(video_id: int, db: AsyncSession = Depends(get_db)):
    video = await db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="動画が見つかりません")

    result = await db.execute(
        select(Receipt)
        .options(selectinload(Receipt.segments))
        .where(Receipt.video_id == video_id)
        .order_by(Receipt.scene_start_frame, Receipt.frame_number, Receipt.id)
    )
    receipts = list(result.scalars().all())
    payload = [_serialize_receipt(receipt) for receipt in receipts]
    return ReceiptListResponse(receipts=payload, total=len(payload))


@router.get("/", response_model=VideoListResponse)
async def list_videos(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Video).order_by(Video.created_at.desc()))
    videos = list(result.scalars().all())
    return VideoListResponse(videos=videos, total=len(videos))
