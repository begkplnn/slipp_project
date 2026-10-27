from datetime import date

from eval.metrics import score
from slipp.schema import Receipt
from slipp.validate import validate


def receipt(**overrides) -> Receipt:
    base = {
        "is_receipt": True, "merchant_name": "Hollow Oak Grocers", "store_location": "Camden",
        "purchase_date": "2026-10-01", "purchase_time": "12:00", "currency": "GBP",
        "line_items": [
            {"description": "SOURDOUGH LOAF", "quantity": 1, "unit_price_minor": 295, "total_minor": 295, "kind": "item"},
            {"description": "OAT DRINK 1L", "quantity": 2, "unit_price_minor": 180, "total_minor": 360, "kind": "item"},
            {"description": "MULTIBUY SAVING", "quantity": 1, "unit_price_minor": None, "total_minor": -50, "kind": "discount"},
        ],
        "subtotal_minor": None, "tax_minor": None, "total_minor": 605,
        "payment_method": "card", "readability": "clear", "low_confidence_fields": [],
    }
    base.update(overrides)
    return Receipt.model_validate(base)


def test_perfect_extraction_scores_one():
    s = score(receipt(), receipt())
    assert s["item_f1"] == 1.0 and s["items_all_correct"] == 1.0 and s["field_total_minor"] == 1.0


def test_ocr_typo_still_matches_but_wrong_price_counts():
    label = receipt()
    items = [i.model_dump() for i in label.line_items]
    items[0]["description"] = "S0URD0UGH LOAF"  # OCR-style typo
    items[1]["total_minor"] = 380
    s = score(receipt(line_items=items), label)
    assert s["item_recall"] == 1.0
    assert s["item_price_accuracy"] == 2 / 3
    assert s["items_all_correct"] == 0.0


def test_merchant_name_normalised():
    assert score(receipt(merchant_name="HOLLOW OAK GROCERS."), receipt())["field_merchant_name"] == 1.0


def test_valid_receipt_has_no_flags():
    assert validate(receipt(), today=date(2026, 10, 2)).flags == []


def test_sum_mismatch_and_future_date_flagged():
    flags = validate(receipt(total_minor=999, purchase_date="2026-12-01"), today=date(2026, 10, 2)).flags
    assert any(f.startswith("sum_mismatch") for f in flags)
    assert "date_in_future" in flags
