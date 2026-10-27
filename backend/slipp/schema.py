"""Receipt schema: the single contract between the LLM, validation, evals and the database.

Design choices (worth repeating in interviews):
- Money is stored as integer minor units (pence), never floats. 0.1 + 0.2 != 0.3 in floats,
  and "line items sum to total" is an exact check, so it needs exact numbers.
- Only fields a brand or the validator needs. No card digits, cashier names, customer names,
  loyalty numbers or barcodes: if we never extract them, we can never leak them (UK GDPR
  data minimisation).
- The model reports which fields it was unsure about. Self-reported confidence is a weak
  signal, so validation rules (sums, dates) decide what gets flagged, not this field alone.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    # extra="forbid" emits additionalProperties: false, which structured outputs require.
    model_config = ConfigDict(extra="forbid")


class ItemKind(str, Enum):
    item = "item"
    discount = "discount"  # multibuy, coupon, price cut; total_minor is negative


class PaymentMethod(str, Enum):
    card = "card"
    cash = "cash"
    mobile = "mobile"
    other = "other"
    unknown = "unknown"


class Readability(str, Enum):
    clear = "clear"
    partial = "partial"  # some text faded/cut off
    poor = "poor"  # most of it unreadable


class LineItem(Strict):
    description: str = Field(description="Item text as printed, e.g. 'SEMI SKIMMED MILK 2L'.")
    quantity: float = Field(description="Units or weight in kg. 1 if not printed.")
    unit_price_minor: int | None = Field(description="Price per unit in minor units (pence), null if not printed.")
    total_minor: int = Field(description="Line total in minor units. Negative for discounts.")
    kind: ItemKind


class Receipt(Strict):
    is_receipt: bool = Field(description="False if the image is not a shopping receipt.")
    merchant_name: str | None = Field(description="Store or brand name as printed.")
    store_location: str | None = Field(description="Branch town/city or street, no postcode needed.")
    purchase_date: str | None = Field(description="ISO date YYYY-MM-DD.")
    purchase_time: str | None = Field(description="24h time HH:MM.")
    currency: str = Field(description="ISO 4217 code, e.g. GBP.")
    line_items: list[LineItem]
    subtotal_minor: int | None
    tax_minor: int | None = Field(description="VAT total if printed separately.")
    total_minor: int | None = Field(description="Amount paid, in minor units.")
    payment_method: PaymentMethod
    readability: Readability
    low_confidence_fields: list[str] = Field(
        description="Names of fields you could not read with confidence, e.g. 'purchase_date' or 'line_items[3].total_minor'."
    )


def receipt_json_schema() -> dict:
    return Receipt.model_json_schema()
