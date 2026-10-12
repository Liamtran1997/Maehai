from datetime import date, datetime

from ninja import Field, Schema


class ItemIn(Schema):
    sku: str
    quantity: int


class AddressIn(Schema):
    address_line: str = ""
    subdistrict: str = ""
    district: str = ""
    province: str = ""
    postal_code: str = ""


class OrderIn(Schema):
    items: list[ItemIn]
    customer_name: str = Field(min_length=1, max_length=120)
    phone: str
    shipping_method: str
    requested_date: date
    address: AddressIn = AddressIn()
    note: str = Field(default="", max_length=300)


class ItemOut(Schema):
    sku: str
    product_name: str
    variant_label: str
    unit_price_satang: int
    quantity: int
    line_total_satang: int


class ShippingOut(Schema):
    code: str
    name: str
    kind: str


class EventOut(Schema):
    created_at: datetime
    kind: str
    detail: str


class PaymentOut(Schema):
    id: int
    status: str
    amount_satang: int
    expires_at: datetime
    qr_payload: str | None = None
    slip_url: str | None = None
    reject_reason: str = ""


class BranchOut(Schema):
    code: str
    name: str


class BranchIn(Schema):
    branch: str


class OrderOut(Schema):
    number: str
    token: str
    status: str
    status_label: str
    customer_name: str
    phone: str
    shipping_method: ShippingOut
    requested_date: date
    address_line: str
    subdistrict: str
    district: str
    province: str
    postal_code: str
    note: str
    items: list[ItemOut]
    subtotal_satang: int
    shipping_fee_satang: int | None
    vat_satang: int
    total_satang: int | None
    tracking_ref: str
    created_at: datetime
    events: list[EventOut]
    payment: PaymentOut | None = None
    fulfillment_branch: BranchOut | None = None
    line_linked: bool = False
    line_link_url: str | None = None


class LookupIn(Schema):
    number: str
    phone: str


class TokenOut(Schema):
    number: str
    token: str


class OrderSummaryOut(Schema):
    number: str
    status: str
    status_label: str
    customer_name: str
    phone: str
    shipping_method: ShippingOut
    requested_date: date
    total_satang: int | None
    created_at: datetime


class FeeIn(Schema):
    fee_satang: int = Field(ge=0, le=10_000_000)


class StatusIn(Schema):
    status: str
    tracking_ref: str = ""


class RejectIn(Schema):
    reason: str = Field(min_length=1, max_length=200)
