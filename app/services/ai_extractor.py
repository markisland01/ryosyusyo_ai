import json
from datetime import date
from pathlib import Path

from google import genai
from google.genai import types
from PIL import Image

from app.config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL = "gemini-2.5-flash"

EXTRACTION_PROMPT = """
あなたは、領収書、クレジットカード明細、銀行通帳の画像から会計入力向けの情報を抽出するアシスタントです。
画像を読み取り、必ず JSON のみを返してください。説明文や Markdown は不要です。

返却形式:
{
  "document_type": "receipt" | "credit_statement" | "bankbook" | "invoice" | "none",
  "items": [
    {
      "document_type": "receipt" | "credit_statement" | "bankbook" | "invoice" | "other" | null,
      "receipt_date": "YYYY-MM-DD" | null,
      "store_name": string | null,
      "total_amount": integer | null,
      "tax_excluded_amount": integer | null,
      "tax_amount": integer | null,
      "tax_8_amount": integer | null,
      "tax_10_amount": integer | null,
      "balance_amount": integer | null,
      "debit_amount": integer | null,
      "credit_amount": integer | null,
      "payment_method": string | null,
      "registration_number": string | null,
      "invoice_type": string | null,
      "account_category": string | null,
      "description": string | null,
      "confidence_score": number
    }
  ]
}

ルール:
- 対象書類でない場合は {"document_type":"none","items":[]} を返す。
- クレジットカード明細や銀行通帳は明細行ごとに items を複数返してよい。
- 金額は整数。通貨記号やカンマは除く。
- 通帳では balance_amount, debit_amount, credit_amount を優先して埋める。
- registration_number は確認できる場合のみ入れる。
- invoice_type は「適格請求書」「区分記載請求書」「対象外」のいずれか。不明なら null。
- payment_method は「現金」「クレジットカード」「口座引落」「振込」「ATM」「電子マネー」「QRコード決済」「その他」から選ぶ。
- account_category は「旅費交通費」「通信費」「消耗品費」「会議費」「接待交際費」「新聞図書費」「地代家賃」「支払手数料」「租税公課」「雑費」「普通預金」「当座預金」「未払金」「その他」から選ぶ。
- 税情報がない明細は tax_* を null にする。
- 不明な値は null にする。
- confidence_score は 0.0 から 1.0。
"""


def _normalize_item(item: dict, default_document_type: str | None) -> dict:
    normalized = dict(item)
    normalized["document_type"] = normalized.get("document_type") or default_document_type or "other"
    receipt_date = normalized.get("receipt_date")
    if isinstance(receipt_date, str) and receipt_date:
        try:
            normalized["receipt_date"] = date.fromisoformat(receipt_date)
        except ValueError:
            normalized["receipt_date"] = None
    return normalized


def extract_receipt_data(ocr_text: str, image_paths: str | list[str]) -> list[dict]:
    """Use Gemini Vision API to extract structured data from a supported document image."""
    content_parts: list[object] = []

    if isinstance(image_paths, str):
        image_paths = [image_paths]

    for image_path in image_paths:
        image_file = Path(image_path)
        if image_file.exists():
            img = Image.open(image_file)
            content_parts.append(img)

    prompt = EXTRACTION_PROMPT
    if ocr_text and ocr_text.strip():
        prompt += "\n\n参考OCRテキスト:\n" + ocr_text

    content_parts.append(prompt)

    response = client.models.generate_content(
        model=MODEL,
        contents=content_parts,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )

    response_text = response.text.strip()
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    data = json.loads(response_text)

    if isinstance(data, dict) and "items" in data:
        items = data.get("items", [])
        document_type = data.get("document_type")
        if document_type == "none" or not items:
            return []
        return [_normalize_item(item, document_type) for item in items]

    if isinstance(data, dict):
        if not data.get("is_receipt", True):
            return []
        return [_normalize_item(data, data.get("document_type"))]

    if isinstance(data, list):
        return [_normalize_item(item, None) for item in data]

    return []
