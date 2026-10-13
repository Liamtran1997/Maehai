from datetime import datetime

from ninja import Field, Schema

from .models import Campaign


class CampaignProductIn(Schema):
    product_id: int


class CampaignIn(Schema):
    name: str = Field(min_length=1, max_length=120)
    theme: str = Campaign.Theme.DEFAULT
    accent_color: str = Field("", max_length=7)
    decorations: bool = True
    starts_at: datetime
    ends_at: datetime
    hero_kind: str = Campaign.HeroKind.NONE
    hero_title: str = Field("", max_length=80)
    hero_subtitle: str = Field("", max_length=160)
    hero_cta_label: str = Field("", max_length=40)
    hero_cta_url: str = Field("", max_length=300)
    bar_enabled: bool = False
    bar_text: str = Field("", max_length=80)
    bar_url: str = Field("", max_length=300)
    collection_title: str = Field("", max_length=80)
    product_ids: list[int] = []


class ProductRef(Schema):
    id: int
    name: str


class CampaignOut(Schema):
    id: int
    name: str
    theme: str
    accent_color: str
    decorations: bool
    starts_at: datetime
    ends_at: datetime
    published_at: datetime | None
    ended_at: datetime | None
    status: str
    status_label: str
    hero_kind: str
    hero_image_url: str | None
    hero_poster_url: str | None
    hero_title: str
    hero_subtitle: str
    hero_cta_label: str
    hero_cta_url: str
    bar_enabled: bool
    bar_text: str
    bar_url: str
    collection_title: str
    products: list[ProductRef]
    created_by: str
    updated_by: str


class CampaignListOut(Schema):
    items: list[CampaignOut]


class PreviewTokenOut(Schema):
    token: str
    expires_in: int
