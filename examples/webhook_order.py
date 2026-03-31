"""Typed webhook ingestion with validators, computed fields, and deep queries."""

import sys
from pathlib import Path as FSPath

sys.path.insert(0, str(FSPath(__file__).resolve().parents[1]))

from modict import MISSING, Query, modict


class LineItem(modict):
    # Required typed fields turn raw JSON dicts into validated item objects.
    sku: str = modict.field(required="always")
    quantity: int = modict.field(required="always")
    unit_price_cents: int = modict.field(required="always")

    @modict.model_validator(mode="after")
    def validate_pricing(self):
        if self["quantity"] <= 0:
            raise ValueError("quantity must be > 0")
        if self["unit_price_cents"] < 0:
            raise ValueError("unit_price_cents must be >= 0")
        return None


class OrderWebhook(modict):
    # "forbid" makes the webhook contract explicit while keeping dict behavior.
    _config = modict.config(extra="forbid")

    event_type: str = modict.field(required="always")
    order_id: str = modict.field(required="always")
    customer_email: str = modict.field(required="always")
    shipping_cents: int = 0
    line_items: list[LineItem] = modict.field(required="always")
    metadata: dict[str, str] = modict.factory(dict)

    @modict.validator("customer_email")
    def normalize_email(self, value):
        # Field validators are a good place to normalize noisy external payloads.
        return value.strip().lower()

    @modict.model_validator(mode="after")
    def validate_order(self):
        if not self["line_items"]:
            raise ValueError("line_items must not be empty")
        return None

    @modict.computed(cache=True, deps=["line_items", "shipping_cents"])
    def total_cents(self) -> int:
        # Computed fields stay inside the dict model instead of living beside it.
        return sum(item.quantity * item.unit_price_cents for item in self.line_items) + self.shipping_cents


def main():
    raw_payload = """
    {
      "event_type": "order.created",
      "order_id": "ord_2026_00042",
      "customer_email": "  Alice@example.com  ",
      "shipping_cents": "490",
      "line_items": [
        {"sku": "keyboard-60", "quantity": "1", "unit_price_cents": "9900"},
        {"sku": "cable-usb-c", "quantity": 2, "unit_price_cents": 1200}
      ],
      "metadata": {"channel": "shopify", "country": "FR"}
    }
    """

    # loads() parses JSON, then applies coercion/validation into the target subclass.
    order = OrderWebhook.loads(raw_payload)

    # The result is still a real dict, but nested items have been typed and coerced.
    assert isinstance(order, dict)
    assert isinstance(order.line_items[0], LineItem)
    assert order.customer_email == "alice@example.com"
    # JSONPath access works directly on the validated object.
    assert order.get_nested("$.line_items[0].sku") == "keyboard-60"
    assert order.total_cents == 12790

    # Query lets you search deep leaves without writing manual traversal code.
    expensive_fields = order.found(
        Query("$.line_items[*].unit_price_cents", lambda cents: cents >= 5000)
    )

    print("Webhook accepted")
    print(f"order_id={order.order_id}")
    print(f"customer_email={order.customer_email}")
    print(f"line_items={len(order.line_items)}")
    print(f"total_cents={order.total_cents}")
    print("expensive_paths=", [str(path) for path in expensive_fields])


if __name__ == "__main__":
    main()
