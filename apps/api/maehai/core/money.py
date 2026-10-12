"""All money is stored as integer satang (1 THB = 100 satang). Never use float."""
from django.conf import settings

SATANG_PER_BAHT = 100


def baht_to_satang(baht: str | int | float) -> int:
    from decimal import ROUND_HALF_UP, Decimal

    return int((Decimal(str(baht)) * SATANG_PER_BAHT).quantize(Decimal("1"), ROUND_HALF_UP))


def vat_included(total_satang: int) -> int:
    """VAT portion of a VAT-inclusive price. 0 if shop is not VAT-registered."""
    if not settings.VAT_ENABLED:
        return 0
    rate = settings.VAT_RATE_PERCENT
    return round(total_satang * rate / (100 + rate))


def format_thb(satang: int) -> str:
    return f"฿{satang / SATANG_PER_BAHT:,.2f}"
