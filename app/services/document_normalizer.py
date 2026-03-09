import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rule import Rule


INVOICE_TYPES = {"適格請求書", "区分記載請求書", "対象外"}
PAYMENT_METHODS = {
    "現金",
    "クレジットカード",
    "口座引落",
    "振込",
    "ATM",
    "電子マネー",
    "QRコード決済",
    "その他",
}
ACCOUNT_CATEGORIES = {
    "旅費交通費",
    "通信費",
    "消耗品費",
    "会議費",
    "接待交際費",
    "新聞図書費",
    "地代家賃",
    "支払手数料",
    "租税公課",
    "雑費",
    "普通預金",
    "当座預金",
    "未払金",
    "その他",
}


async def load_active_rules(db: AsyncSession) -> list[Rule]:
    result = await db.execute(
        select(Rule)
        .where(Rule.enabled.is_(True))
        .order_by(Rule.rule_type.asc(), Rule.priority.asc(), Rule.id.asc())
    )
    return list(result.scalars().all())


def _text_blob(item: dict) -> str:
    return " ".join(
        str(v).lower()
        for v in [
            item.get("store_name"),
            item.get("description"),
            item.get("payment_method"),
            item.get("account_category"),
            item.get("invoice_type"),
            item.get("ocr_raw_text"),
        ]
        if v
    )


def _find_rule_match(item: dict, rules: list[Rule] | None, rule_type: str) -> str | None:
    if not rules:
        return None

    text = _text_blob(item)
    document_type = item.get("document_type")

    for rule in rules:
        if rule.rule_type != rule_type:
            continue
        if rule.document_type and rule.document_type != document_type:
            continue
        if rule.pattern.lower() in text:
            return rule.target_value
    return None


def normalize_invoice_type(item: dict, rules: list[Rule] | None = None) -> str | None:
    document_type = item.get("document_type")
    registration_number = item.get("registration_number")
    invoice_type = item.get("invoice_type")

    matched = _find_rule_match(item, rules, "invoice_type")
    if matched in INVOICE_TYPES:
        return matched

    if document_type in {"credit_statement", "bankbook"}:
        return "対象外"

    if isinstance(registration_number, str) and re.fullmatch(r"T\d{13}", registration_number):
        return "適格請求書"

    if invoice_type in INVOICE_TYPES:
        return invoice_type

    has_tax_info = any(
        item.get(key) not in (None, 0, "") for key in ["tax_amount", "tax_8_amount", "tax_10_amount"]
    )
    if document_type in {"receipt", "invoice"} and has_tax_info:
        return "区分記載請求書"

    return "対象外" if document_type in {"credit_statement", "bankbook"} else None


def normalize_payment_method(item: dict, rules: list[Rule] | None = None) -> str:
    document_type = item.get("document_type")
    text = _text_blob(item)
    raw = item.get("payment_method")

    matched = _find_rule_match(item, rules, "payment_method")
    if matched in PAYMENT_METHODS:
        return matched

    if raw in PAYMENT_METHODS:
        return raw

    keyword_mapping = [
        (["paypay", "楽天ペイ", "d払い", "au pay", "メルペイ", "qr"], "QRコード決済"),
        (["quicpay", "交通系ic", "edy", "waon", "nanaco", " id ", "電子マネー"], "電子マネー"),
        (["visa", "mastercard", "jcb", "amex", "クレジット", "card"], "クレジットカード"),
        (["口座振替", "自動引落", "口座引落", "引落"], "口座引落"),
        (["振込", "振替", "送金"], "振込"),
        (["atm"], "ATM"),
        (["現金", "cash"], "現金"),
    ]
    for keywords, method in keyword_mapping:
        if any(keyword in text for keyword in keywords):
            return method

    if document_type == "credit_statement":
        return "クレジットカード"
    if document_type == "bankbook":
        return "口座引落"
    if document_type in {"receipt", "invoice"}:
        return "現金"
    return "その他"


def normalize_account_category(item: dict, rules: list[Rule] | None = None) -> str:
    document_type = item.get("document_type")
    payment_method = item.get("payment_method")
    text = _text_blob(item)
    raw = item.get("account_category")

    matched = _find_rule_match(item, rules, "account_category")
    if matched in ACCOUNT_CATEGORIES:
        return matched

    if raw in ACCOUNT_CATEGORIES:
        return raw

    if document_type == "credit_statement":
        return "未払金"

    if document_type == "bankbook":
        if any(keyword in text for keyword in ["手数料", "振込手数料", "atm手数料"]):
            return "支払手数料"
        if "当座" in text:
            return "当座預金"
        return "普通預金"

    keyword_mapping = [
        (["駐車場", "タクシー", "jr", "近鉄", "高速", "ガソリン"], "旅費交通費"),
        (["amazon", "文具", "ドラッグ", "ホームセンター", "家電"], "消耗品費"),
        (["レストラン", "カフェ", "居酒屋", "会食", "bbq", "pizza"], "会議費"),
        (["書店", "新聞", "雑誌", "kindle"], "新聞図書費"),
        (["印紙", "税", "公課"], "租税公課"),
        (["手数料"], "支払手数料"),
        (["家賃"], "地代家賃"),
        (["電話", "通信", "インターネット"], "通信費"),
    ]
    for keywords, category in keyword_mapping:
        if any(keyword.lower() in text for keyword in keywords):
            return category

    if payment_method == "クレジットカード":
        return "未払金"

    return "雑費"


def normalize_document_fields(item: dict, rules: list[Rule] | None = None) -> dict:
    normalized = dict(item)
    normalized["invoice_type"] = normalize_invoice_type(normalized, rules)
    normalized["payment_method"] = normalize_payment_method(normalized, rules)
    normalized["account_category"] = normalize_account_category(normalized, rules)
    return normalized
