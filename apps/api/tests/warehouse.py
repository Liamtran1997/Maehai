"""Helpers that move stock the way staff do now: a receipt at the central warehouse, then a transfer and its
confirmation at a branch. Tests use these instead of the old one-step adjust/transfer."""
from maehai.inventory.models import Source

JSON = "application/json"
CENTRAL = "srinarong"


def _source():
    return Source.objects.get_or_create(name="ทดสอบ", defaults={"kind": "buy"})[0]


def stock_in(client, branch: str, sku: str, qty) -> None:
    """Put qty of a sellable size on the shelf of `branch`, through the proper slips."""
    r = client.post("/api/admin/inventory/documents/receipts",
                    {"source_id": _source().id, "lines": [{"sku": sku, "quantity": qty}]}, content_type=JSON)
    assert r.status_code == 201, r.content
    if branch == CENTRAL:
        return
    send_and_confirm(client, branch, [(sku, qty)])


def send_and_confirm(client, branch: str, items, received=None) -> dict:
    """Send lines from the central warehouse to `branch`, then have the branch count them in."""
    lines = [{"sku": s, "quantity": q} for s, q in items]
    r = client.post("/api/admin/inventory/documents/transfers",
                    {"to_branch": branch, "vehicle": "กระบะทดสอบ", "lines": lines}, content_type=JSON)
    assert r.status_code == 201, r.content
    doc = r.json()
    answers = []
    for ln in doc["lines"]:
        got = ln["sent"] if received is None else received.get(ln["sku"] or ln["material_code"], ln["sent"])
        answers.append({"line_id": ln["id"], "received": got})
    # The owner is not the branch's own manager, so confirming counts as a substitute: a reason is required.
    r2 = client.post(f"/api/admin/inventory/documents/{doc['number']}/receive",
                     {"lines": answers, "substitute_reason": "ทดสอบ"}, content_type=JSON)
    assert r2.status_code == 200, r2.content
    return r2.json()
