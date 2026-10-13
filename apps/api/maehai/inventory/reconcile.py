"""Stock reconciliation for one place over a date range: opening + movements = closing, for every item.

Goods still on a truck are shown separately (in transit). Goods lost or thrown away are shown from the slips,
because they never come back to on_hand: they leave the books of the warehouse when the slip is closed.
"""
from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from .models import Document, DocumentLine, Material, MaterialLevel, MaterialMovement, StockLevel, StockMovement

ZERO = Decimal(0)


def _fmt(value) -> str:
    """Plain decimal text without trailing zeros: 2 -> "2", 2.500 -> "2.5"."""
    return format(Decimal(value).normalize(), "f")


def _day_bounds(date_from, date_to):
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(date_from, time.min), tz)
    end = timezone.make_aware(datetime.combine(date_to + timedelta(days=1), time.min), tz)
    return start, end


def _row(kind, obj_id, name, unit):
    return {"kind": kind, "id": obj_id, "name": name, "unit": unit, "opening": ZERO, "flows": defaultdict(lambda: ZERO),
            "closing": ZERO, "on_hand": ZERO, "in_transit_out": ZERO, "in_transit_in": ZERO,
            "lost": ZERO, "discarded": ZERO, "refused": ZERO}


def reconcile(branch, date_from, date_to) -> dict:
    from maehai.catalog.models import ProductVariant

    start, end = _day_bounds(date_from, date_to)
    rows: dict[tuple, dict] = {}

    def row_for(key, make):
        if key not in rows:
            rows[key] = make()
        return rows[key]

    # ---- movements: opening (everything before the range) and flows inside it
    for model, kind, id_field in ((StockMovement, "product", "variant_id"), (MaterialMovement, "material", "material_id")):
        before = model.objects.filter(branch=branch, created_at__lt=start).values(id_field).annotate(t=Sum("delta"))
        during = model.objects.filter(branch=branch, created_at__gte=start, created_at__lt=end) \
            .values(id_field, "reason").annotate(t=Sum("delta"))
        for r in before:
            key = (kind, r[id_field])
            row_for(key, lambda: _blank(kind, r[id_field], branch))["opening"] += Decimal(r["t"] or 0)
        for r in during:
            key = (kind, r[id_field])
            row = row_for(key, lambda: _blank(kind, r[id_field], branch))
            row["flows"][r["reason"]] += Decimal(r["t"] or 0)

    # ---- current on-hand, so every row can be checked against its ledger
    for lv in StockLevel.objects.filter(branch=branch).select_related("variant"):
        row_for(("product", lv.variant_id), lambda: _blank("product", lv.variant_id, branch))["on_hand"] = Decimal(lv.on_hand)
    for ml in MaterialLevel.objects.filter(branch=branch):
        row_for(("material", ml.material_id), lambda: _blank("material", ml.material_id, branch))["on_hand"] = ml.on_hand

    # ---- slips: in transit now, and losses/refusals closed inside the range
    for ln in DocumentLine.objects.filter(document__status__in=[Document.Status.SENT, Document.Status.SENT_BACK]) \
            .filter(document__from_branch=branch).select_related("document"):
        row = row_for(_key(ln), lambda: _blank(_kind(ln), _obj_id(ln), branch))
        row["in_transit_out"] += ln.sent
    for ln in DocumentLine.objects.filter(document__status__in=[Document.Status.SENT, Document.Status.SENT_BACK]) \
            .filter(document__to_branch=branch).select_related("document"):
        row = row_for(_key(ln), lambda: _blank(_kind(ln), _obj_id(ln), branch))
        row["in_transit_in"] += ln.sent
    closed = DocumentLine.objects.filter(document__closed_at__gte=start, document__closed_at__lt=end)
    for ln in closed.filter(document__to_branch=branch).select_related("document"):
        row = row_for(_key(ln), lambda: _blank(_kind(ln), _obj_id(ln), branch))
        row["lost"] += ln.missing
        row["discarded"] += ln.discarded
        if ln.document.kind == Document.Kind.TRANSFER:
            row["refused"] += ln.refused

    out = []
    for key, row in rows.items():
        flows = {k: _fmt(v) for k, v in row["flows"].items()}
        closing = row["opening"] + sum(row["flows"].values(), ZERO)
        out.append({
            "kind": row["kind"], "id": row["id"], "name": row["name"], "unit": row["unit"],
            "opening": _fmt(row["opening"]), "flows": flows, "closing": _fmt(closing),
            "on_hand": _fmt(row["on_hand"]), "balanced": closing == row["on_hand"],
            "in_transit_out": _fmt(row["in_transit_out"]), "in_transit_in": _fmt(row["in_transit_in"]),
            "lost": _fmt(row["lost"]), "discarded": _fmt(row["discarded"]), "refused": _fmt(row["refused"]),
        })
    out.sort(key=lambda r: (r["kind"], r["name"]))
    return {"branch": branch.code, "from": date_from.isoformat(), "to": date_to.isoformat(), "rows": out,
            "unbalanced": sum(1 for r in out if not r["balanced"])}


def _blank(kind, obj_id, branch):
    if kind == "product":
        from maehai.catalog.models import ProductVariant

        v = ProductVariant.objects.select_related("product").get(pk=obj_id)
        return _row(kind, obj_id, f"{v.product.name} ({v.label})", "ชิ้น")
    m = Material.objects.get(pk=obj_id)
    return _row(kind, obj_id, m.name, m.unit)


def _key(ln: DocumentLine):
    return ("product", ln.variant_id) if ln.variant_id else ("material", ln.material_id)


def _kind(ln: DocumentLine) -> str:
    return "product" if ln.variant_id else "material"


def _obj_id(ln: DocumentLine):
    return ln.variant_id or ln.material_id
