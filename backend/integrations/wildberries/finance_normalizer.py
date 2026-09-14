from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID


def pick(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in item and item[key] is not None:
            return item[key]
    return None


def to_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default


def optional_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    converted = to_int(value, default=-1)
    return None if converted == -1 else converted


def decimal_value(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value).replace(",", "."))
    except Exception:
        return Decimal("0")


def text(value: Any) -> Optional[str]:
    return None if value is None else str(value)


def date_value(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def datetime_value(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
        except ValueError:
            parsed_date = date_value(value)
            return (
                datetime.combine(parsed_date, datetime.min.time(), tzinfo=timezone.utc)
                if parsed_date
                else None
            )
    return None


def normalize_finance_row(item: dict[str, Any], user_id: UUID, account_id: UUID) -> dict[str, Any]:
    rrd_id = optional_int(pick(item, "rrdId", "rrd_id"))
    nm_id = optional_int(pick(item, "nmId", "nm_id"))
    rr_date = date_value(pick(item, "rrDate", "rrDt", "rr_dt"))
    operation = text(pick(item, "sellerOperName", "supplierOperName", "supplier_oper_name"))

    if not rrd_id or not nm_id or rr_date is None or not operation:
        raise ValueError("WB finance row is missing required identity fields")

    return {
        "user_id": user_id,
        "token_id": account_id,
        "rr_dt": rr_date,
        "order_dt": datetime_value(pick(item, "orderDt", "order_dt")),
        "sale_dt": datetime_value(pick(item, "saleDt", "sale_dt")),
        "date_from": date_value(pick(item, "dateFrom", "date_from")),
        "date_to": date_value(pick(item, "dateTo", "date_to")),
        "create_dt": datetime_value(pick(item, "createDate", "createDt", "create_dt")),
        "nm_id": nm_id,
        "rrd_id": rrd_id,
        "gi_id": optional_int(pick(item, "giId", "gi_id")),
        "shk_id": optional_int(pick(item, "shkId", "shk_id")),
        "srid": text(pick(item, "srid", "SRID")),
        "realization_report_id": optional_int(pick(item, "reportId", "realizationReportId")),
        "supplier_oper_name": operation,
        "doc_type_name": text(pick(item, "docTypeName", "doc_type_name")),
        "subject_name": text(pick(item, "subjectName", "subject_name")),
        "brand_name": text(pick(item, "brandName", "brand_name")),
        "sa_name": text(pick(item, "vendorCode", "saName", "sa_name")),
        "ts_name": text(pick(item, "techSize", "tsName", "ts_name")),
        "barcode": text(pick(item, "sku", "barcode")),
        "title": text(pick(item, "title", "Title")),
        "office_name": text(pick(item, "officeName", "office_name")),
        "gi_box_type_name": text(pick(item, "giBoxTypeName", "gi_box_type_name")),
        "ppvz_office_id": optional_int(pick(item, "ppvzOfficeId", "ppvz_office_id")),
        "ppvz_office_name": text(pick(item, "ppvzOfficeName", "ppvz_office_name")),
        "quantity": to_int(pick(item, "quantity", "Quantity")),
        "retail_price": decimal_value(pick(item, "retailPrice", "retail_price")),
        "retail_amount": decimal_value(pick(item, "retailAmount", "retail_amount")),
        "retail_price_with_disc_rub": decimal_value(pick(item, "retailPriceWithDisc", "retailPriceWithdiscRub")),
        "sale_percent": decimal_value(pick(item, "salePercent", "sale_percent")),
        "commission_percent": decimal_value(pick(item, "commissionPercent", "commission_percent")),
        "product_discount_for_report": decimal_value(pick(item, "productDiscountForReport")),
        "ppvz_spp_prc": decimal_value(pick(item, "spp", "ppvzSppPrc")),
        "ppvz_kvw_prc_base": decimal_value(pick(item, "kvwBase", "ppvzKvwPrcBase")),
        "ppvz_kvw_prc": decimal_value(pick(item, "kvw", "ppvzKvwPrc")),
        "sup_rating_prc_up": decimal_value(pick(item, "supRatingUp", "supRatingPrcUp")),
        "is_kgvp_v2": decimal_value(pick(item, "isKgvpV2")),
        "ppvz_for_pay": decimal_value(pick(item, "forPay", "ppvzForPay")),
        "ppvz_sales_commission": decimal_value(pick(item, "ppvzSalesCommission")),
        "ppvz_reward": decimal_value(pick(item, "ppvzReward")),
        "ppvz_vw": decimal_value(pick(item, "vw", "ppvzVw")),
        "ppvz_vw_nds": decimal_value(pick(item, "vwNds", "ppvzVwNds")),
        "delivery_amount": to_int(pick(item, "deliveryAmount")),
        "return_amount": to_int(pick(item, "returnAmount")),
        "delivery_rub": decimal_value(pick(item, "deliveryService", "deliveryRub")),
        "return_rub": decimal_value(pick(item, "returnRub")),
        "rebill_logistic_cost": decimal_value(pick(item, "rebillLogisticCost")),
        "rebill_logistic_org": text(pick(item, "rebillLogisticOrg")),
        "storage_fee": decimal_value(pick(item, "paidStorage", "storageFee")),
        "acceptance": decimal_value(pick(item, "paidAcceptance", "acceptance")),
        "penalty": decimal_value(pick(item, "penalty")),
        "additional_payment": decimal_value(pick(item, "additionalPayment")),
        "deduction": decimal_value(pick(item, "deduction")),
        "acquiring_fee": decimal_value(pick(item, "acquiringFee")),
        "acquiring_bank": text(pick(item, "acquiringBank")),
        "supplier_promo": text(pick(item, "sellerPromo", "supplierPromo")),
        "order_uid": text(pick(item, "orderUid")),
        "kiz": text(pick(item, "kiz")),
        "declaration_number": text(pick(item, "declarationNumber")),
        "ppvz_supplier_id": optional_int(pick(item, "ppvzSupplierId")),
        "ppvz_supplier_name": text(pick(item, "ppvzSupplierName")),
        "ppvz_inn": text(pick(item, "ppvzSupplierInn", "ppvzInn")),
        "currency_name": text(pick(item, "currency", "currencyName")),
        "report_type": optional_int(pick(item, "reportType")),
        "trbx_id": text(pick(item, "trbxId")),
        "created_at": datetime.now(timezone.utc),
    }
