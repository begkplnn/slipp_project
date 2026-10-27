"""Deterministic checks on an extracted receipt. Code decides, not the LLM.

Week 1 has the arithmetic and plausibility checks. Duplicate detection (image hash +
store/date/total) needs the database and comes with the upload flow.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from slipp.schema import Receipt

MAX_RECEIPT_AGE_DAYS = 90
MAX_TOTAL_MINOR = 100_000  # £1,000: anything above goes to manual review
SUM_TOLERANCE_MINOR = 1  # rounding on weighed items


@dataclass
class ValidationReport:
    flags: list[str] = field(default_factory=list)

    @property
    def needs_confirmation(self) -> bool:
        return bool(self.flags)


def validate(receipt: Receipt, today: date | None = None) -> ValidationReport:
    today = today or date.today()
    report = ValidationReport()

    if not receipt.is_receipt:
        report.flags.append("not_a_receipt")
        return report

    if receipt.total_minor is None:
        report.flags.append("missing_total")
    else:
        items_sum = sum(i.total_minor for i in receipt.line_items)
        if abs(items_sum - receipt.total_minor) > SUM_TOLERANCE_MINOR:
            report.flags.append(f"sum_mismatch: items={items_sum} total={receipt.total_minor}")
        if receipt.total_minor <= 0 or receipt.total_minor > MAX_TOTAL_MINOR:
            report.flags.append("implausible_total")

    if receipt.purchase_date is None:
        report.flags.append("missing_date")
    else:
        try:
            d = date.fromisoformat(receipt.purchase_date)
            if d > today:
                report.flags.append("date_in_future")
            elif d < today - timedelta(days=MAX_RECEIPT_AGE_DAYS):
                report.flags.append("date_too_old")
        except ValueError:
            report.flags.append("invalid_date")

    if receipt.readability != "clear" or receipt.low_confidence_fields:
        report.flags.append("low_confidence")

    return report
