"""Thai message wording. Short, one action per message, always with the link to act on."""
from django.conf import settings

from maehai.core.money import format_thb
from maehai.core.thai import thai_date


def _order_url(order) -> str:
    return f"{settings.PUBLIC_SHOP_URL}/orders/{order.number}?t={order.public_token}"


def _admin_url(order) -> str:
    return f"{settings.ADMIN_URL}/orders/{order.number}"


def staff_new_order(order) -> str:
    action = "ต้องแจ้งค่าจัดส่ง" if order.shipping_fee_satang is None else "รอลูกค้าชำระเงิน"
    return (f"คำสั่งซื้อใหม่ {order.number}\n{order.customer_name} · {order.shipping_method.name}\n"
            f"สินค้า {format_thb(order.subtotal_satang)} · นัดรับ {thai_date(order.requested_date)}\n{action}\n{_admin_url(order)}")


def staff_slip(order, amount_satang: int) -> str:
    return f"ลูกค้าแนบสลิป {order.number}\nยอด {format_thb(amount_satang)}\nตรวจสลิป: {_admin_url(order)}"


def staff_low_stock(variant, branch, available: int) -> str:
    what = "หมดแล้ว" if available <= 0 else f"เหลือ {available}"
    return f"สต็อกใกล้หมด {branch.name}\n{variant.product.name} ({variant.label}) {what}\nเติมสต็อกที่: {settings.ADMIN_URL}/inventory"


def customer_fee_quoted(order) -> str:
    return (f"ร้านแม่ฮายแจ้งค่าจัดส่งแล้ว\nคำสั่งซื้อ {order.number}\nค่าจัดส่ง {format_thb(order.shipping_fee_satang)} "
            f"· รวมทั้งสิ้น {format_thb(order.total_satang)}\nเปิดลิงก์เพื่อชำระเงินผ่าน PromptPay:\n{_order_url(order)}")


def customer_paid(order) -> str:
    return f"ได้รับการชำระเงินแล้ว {format_thb(order.total_satang)}\nคำสั่งซื้อ {order.number} ร้านกำลังจัดเตรียมสินค้า นัดรับ {thai_date(order.requested_date)}\n{_order_url(order)}"


def customer_slip_rejected(order, reason: str) -> str:
    return f"สลิปของคำสั่งซื้อ {order.number} ไม่ผ่าน: {reason}\nกรุณาตรวจสอบและแนบใหม่:\n{_order_url(order)}"


def customer_shipped(order) -> str:
    ref = f"\nเลขใบฝากส่ง/พัสดุ: {order.tracking_ref}" if order.tracking_ref else ""
    return f"ร้านจัดส่งสินค้าแล้ว\nคำสั่งซื้อ {order.number} ผ่าน {order.shipping_method.name}{ref}\nดูรายละเอียด: {_order_url(order)}"


def customer_cancelled(order) -> str:
    return f"คำสั่งซื้อ {order.number} ถูกยกเลิก\nหากชำระเงินแล้วหรือมีข้อสงสัย ติดต่อร้านทาง LINE นี้ได้เลย"


def link_ok(order) -> str:
    return f"เชื่อมต่อ LINE กับคำสั่งซื้อ {order.number} แล้ว\nร้านจะแจ้งเมื่อมีค่าจัดส่ง ได้รับเงิน และจัดส่งสินค้า"


def customer_restocked(variant) -> str:
    return (f"{variant.product.name} ({variant.label}) กลับมามีของแล้ว\nสั่งได้เลยที่: "
            f"{settings.PUBLIC_SHOP_URL}/products/{variant.product.slug}\n(จำนวนจำกัด ร้านไม่ได้กันของไว้ให้)")


def restock_ok(variant) -> str:
    return f"รับทราบ ร้านจะแจ้งทาง LINE นี้เมื่อ {variant.product.name} ({variant.label}) กลับมามีของ"


def restock_in_stock(variant) -> str:
    return f"{variant.product.name} ({variant.label}) ตอนนี้มีของอยู่แล้ว สั่งได้เลยที่ {settings.PUBLIC_SHOP_URL}/products/{variant.product.slug}"


LINK_HELP = "ส่งข้อความจากหน้าคำสั่งซื้อบนเว็บเพื่อเชื่อมต่อ LINE (กดปุ่ม “รับแจ้งเตือนทาง LINE”)"


def _items_summary(doc, limit: int = 4) -> str:
    lines = list(doc.lines.select_related("variant__product", "material"))
    names = [(ln.variant.product.name if ln.variant_id else ln.material.name) for ln in lines]
    more = f" และอีก {len(names) - limit} รายการ" if len(names) > limit else ""
    return ", ".join(names[:limit]) + more


def staff_transfer_sent(doc) -> str:
    vehicle = f" · รถ {doc.vehicle}" if doc.vehicle else ""
    return (f"มีของส่งมาถึง {doc.to_branch.name}\nใบส่ง {doc.number}{vehicle}\n{_items_summary(doc)}\n"
            f"กรุณาตรวจรับในระบบ: {settings.ADMIN_URL}/inventory")


def staff_transfer_discrepancy(doc, return_doc) -> str:
    back = f"\nของที่ไม่รับกลับคลังกลาง: ใบคืน {return_doc.number}" if return_doc else ""
    return (f"การรับของไม่ครบ {doc.number} ({doc.to_branch.name})\n"
            f"สถานะ: {doc.get_status_display()}{back}\nดูรายละเอียด: {settings.ADMIN_URL}/inventory")


def staff_return_sent(doc) -> str:
    return (f"มีของส่งคืนคลังกลาง {doc.number} จาก {doc.from_branch.name}\n{_items_summary(doc)}\n"
            f"กรุณารับในระบบ: {settings.ADMIN_URL}/inventory")


def staff_stock_overdue(doc) -> str:
    return (f"ใบ {doc.number} ยังไม่ได้รับยืนยันเกิน 24 ชั่วโมง\n"
            f"{doc.from_branch.name} → {doc.to_branch.name}\nตรวจสอบ: {settings.ADMIN_URL}/inventory")
