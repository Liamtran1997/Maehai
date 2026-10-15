from ninja import Field, Schema


class ProductImageOut(Schema):
    id: int
    url: str


class CategoryOut(Schema):
    name: str
    slug: str


class VariantOut(Schema):
    id: int
    label: str
    sku: str
    price_satang: int                       # selling price now (after promotion). Admin endpoints return the list price here.
    original_price_satang: int | None = None  # list price, only when a promotion lowers it
    promotion_label: str | None = None        # e.g. "ลด 10%"
    weight_grams: int | None
    available: int | None = None   # units still buyable; null = not counted (always available)
    restock_alert_url: str | None = None  # LINE link to ask for a back-in-stock message (sold-out tracked variants only)


class ProductListOut(Schema):
    slug: str
    name: str
    subtitle: str
    category: CategoryOut
    badge: str
    bands: list[str]
    image_url: str | None = None
    price_from_satang: int
    original_price_from_satang: int | None = None
    promotion_label: str | None = None
    in_stock: bool = True


class PromotionBrief(Schema):
    name: str
    label: str
    ends_at: str | None


class ProductOut(ProductListOut):
    description: str
    ingredients: str
    fda_number: str
    storage_note: str
    variants: list[VariantOut]
    images: list[ProductImageOut] = []
    promotion: PromotionBrief | None = None


class VariantIn(Schema):
    label: str = Field(min_length=1, max_length=60)
    sku: str = Field(min_length=1, max_length=40)
    price_satang: int = Field(gt=0)
    weight_grams: int | None = Field(default=None, gt=0)
    is_active: bool = True


class ProductIn(Schema):
    category_slug: str
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)
    name: str = Field(min_length=1, max_length=150)
    name_en: str = ""
    subtitle: str = ""
    description: str = ""
    ingredients: str = Field(default="", max_length=2000)
    bands: list[str] = []
    badge: str = ""
    fda_number: str = ""
    storage_note: str = ""
    is_active: bool = True
    is_featured: bool = False
    sort_order: int = Field(default=0, ge=0, le=32767)
    variants: list[VariantIn] = Field(min_length=1)


class AdminProductOut(ProductOut):
    id: int
    is_active: bool
    is_featured: bool
    sort_order: int
    name_en: str
