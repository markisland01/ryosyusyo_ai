import csv
import io

from app.models.receipt import Receipt


def export_generic_csv(receipts: list[Receipt], encoding: str = "utf-8-sig") -> str:
    """Export receipts to a generic CSV format with all core fields."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(
        [
            "No",
            "日付",
            "店舗名",
            "合計金額",
            "税抜金額",
            "消費税額",
            "8%対象額",
            "10%対象額",
            "支払方法",
            "登録番号",
            "請求書区分",
            "勘定科目",
            "摘要",
        ]
    )

    for i, receipt in enumerate(receipts, 1):
        writer.writerow(
            [
                i,
                receipt.receipt_date.isoformat() if receipt.receipt_date else "",
                receipt.store_name or "",
                receipt.total_amount or "",
                receipt.tax_excluded_amount or "",
                receipt.tax_amount or "",
                receipt.tax_8_amount or "",
                receipt.tax_10_amount or "",
                receipt.payment_method or "",
                receipt.registration_number or "",
                receipt.invoice_type.value if receipt.invoice_type else "",
                receipt.account_category or "",
                receipt.description or "",
            ]
        )

    return output.getvalue()


def export_yayoi_csv(receipts: list[Receipt], encoding: str = "utf-8-sig") -> str:
    """Export receipts in a simple Yayoi-compatible journal format."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["日付", "借方勘定科目", "借方金額", "貸方勘定科目", "貸方金額", "摘要"])

    for receipt in receipts:
        date_str = receipt.receipt_date.strftime("%Y/%m/%d") if receipt.receipt_date else ""
        credit_account = _payment_to_account(receipt.payment_method)
        summary = f"{receipt.store_name or ''} {receipt.description or ''}".strip()

        writer.writerow(
            [
                date_str,
                receipt.account_category or "雑費",
                receipt.total_amount or 0,
                credit_account,
                receipt.total_amount or 0,
                summary,
            ]
        )

    return output.getvalue()


def export_freee_csv(receipts: list[Receipt], encoding: str = "utf-8-sig") -> str:
    """Export receipts in a simplified freee import format."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(
        [
            "取引の種類",
            "管理番号",
            "発生日",
            "決済期日",
            "勘定科目",
            "税区分",
            "金額",
            "取引先",
            "内容",
            "メモ",
            "決済口座",
        ]
    )

    for i, receipt in enumerate(receipts, 1):
        date_str = receipt.receipt_date.isoformat() if receipt.receipt_date else ""
        tax_category = _get_freee_tax_category(receipt)

        writer.writerow(
            [
                "支出",
                i,
                date_str,
                date_str,
                receipt.account_category or "雑費",
                tax_category,
                receipt.total_amount or 0,
                receipt.store_name or "",
                receipt.description or "",
                f"登録番号:{receipt.registration_number}" if receipt.registration_number else "",
                _payment_to_freee_account(receipt.payment_method),
            ]
        )

    return output.getvalue()


def export_moneyforward_csv(receipts: list[Receipt], encoding: str = "utf-8-sig") -> str:
    """Export receipts in a simplified Money Forward journal format."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(
        [
            "取引日",
            "借方勘定科目",
            "借方補助科目",
            "借方税区分",
            "借方金額",
            "貸方勘定科目",
            "貸方補助科目",
            "貸方税区分",
            "貸方金額",
            "摘要",
        ]
    )

    for receipt in receipts:
        date_str = receipt.receipt_date.isoformat() if receipt.receipt_date else ""
        credit_account = _payment_to_account(receipt.payment_method)
        tax_category = _get_mf_tax_category(receipt)
        summary = f"{receipt.store_name or ''} {receipt.description or ''}".strip()

        writer.writerow(
            [
                date_str,
                receipt.account_category or "雑費",
                "",
                tax_category,
                receipt.total_amount or 0,
                credit_account,
                "",
                "対象外",
                receipt.total_amount or 0,
                summary,
            ]
        )

    return output.getvalue()


def _payment_to_account(payment_method: str | None) -> str:
    mapping = {
        "現金": "現金",
        "クレジットカード": "未払金",
        "電子マネー": "未払金",
        "QRコード決済": "未払金",
    }
    return mapping.get(payment_method or "", "現金")


def _payment_to_freee_account(payment_method: str | None) -> str:
    mapping = {
        "現金": "現金",
        "クレジットカード": "クレジットカード",
        "電子マネー": "その他の決済口座",
        "QRコード決済": "その他の決済口座",
    }
    return mapping.get(payment_method or "", "現金")


def _get_freee_tax_category(receipt: Receipt) -> str:
    if receipt.tax_8_amount and receipt.tax_10_amount:
        return "課対仕入 10%"
    if receipt.tax_8_amount:
        return "課対仕入 8%(軽)"
    return "課対仕入 10%"


def _get_mf_tax_category(receipt: Receipt) -> str:
    if receipt.tax_8_amount and not receipt.tax_10_amount:
        return "課税仕入8%"
    return "課税仕入10%"


EXPORTERS = {
    "generic": export_generic_csv,
    "yayoi": export_yayoi_csv,
    "freee": export_freee_csv,
    "moneyforward": export_moneyforward_csv,
}
