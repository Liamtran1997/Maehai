"""The one place that decides what a variant sells for right now.

The shop, the product pages and order creation all call this, so the price a customer sees is the price they pay.
"""
from dataclasses import dataclass
from datetime import datetime

from django.db.models import Q
from django.utils import timezone

from .models import Promotion


@dataclass(frozen=True)
class Price:
    list_satang: int
    satang: int                      # what the customer pays per unit
    promotion: Promotion | None = None

    @property
    def discounted(self) -> bool:
        return self.satang < self.list_satang


def active_promotions(at: datetime | None = None) -> list[Promotion]:
    at = at or timezone.now()
    qs = (Promotion.objects.filter(is_active=True, starts_at__lte=at).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=at))
          .prefetch_related("products", "categories"))
    promos = list(qs)
    for p in promos:  # cache id sets once instead of querying per variant
        p._product_ids = {x.id for x in p.products.all()}
        p._category_ids = {x.id for x in p.categories.all()}
    return promos


def _covers(promo: Promotion, variant) -> bool:
    if promo.scope == Promotion.Scope.ALL:
        return True
    if promo.scope == Promotion.Scope.PRODUCTS:
        return variant.product_id in promo._product_ids
    return variant.product.category_id in promo._category_ids


def price_of(variant, promos: list[Promotion]) -> Price:
    best, best_off = None, 0
    for p in promos:
        if _covers(p, variant):
            off = p.discount_for(variant.price_satang)
            if off > best_off:  # biggest single discount wins; ties keep the first (newest start)
                best, best_off = p, off
    return Price(variant.price_satang, variant.price_satang - best_off, best)


def prices_for(variants, at: datetime | None = None) -> dict[int, Price]:
    """Prices for many variants with one promotions query. Variants need product (and product.category_id) loaded."""
    promos = active_promotions(at)
    return {v.id: price_of(v, promos) for v in variants}
