from django.core.management.base import BaseCommand

from maehai.shipping.models import ShippingMethod

K = ShippingMethod.Kind
METHODS = [
    ("pickup-srinarong", "รับที่ร้าน สาขาศรีณรงค์", K.PICKUP, "173 ถ.ศรีณรงค์ ต.ในเมือง อ.เมือง จ.อุบลราชธานี"),
    ("pickup-changsanit", "รับที่ร้าน สาขาแจ้งสนิท", K.PICKUP, "42 หมู่ที่ 9 ถ.แจ้งสนิท ต.แจระแม อ.เมือง จ.อุบลราชธานี"),
    ("cargo-ubon", "สหฯอุบลคาร์โก้", K.CARRIER, "รับของที่สะพานขาว กรุงเทพฯ 06:00 ถึง 12:00 น. รถวิ่งทุกวัน ยกเว้นวันเสาร์"),
    ("nakhonchai-air", "นครชัยแอร์", K.CARRIER, "คิดค่าบริการตามน้ำหนัก กล่องละไม่เกิน 20 กก."),
    ("sanguan-chai", "สงวนชัยทัวร์", K.CARRIER, "อุบล ยโสธร ร้อยเอ็ด มหาสารคาม ขอนแก่น อุดรธานี"),
    ("srimongkol", "ศรีมงคล", K.CARRIER, "ชลบุรี พัทยา ศรีราชา"),
    ("train", "สถานีรถไฟ", K.CARRIER, "ผู้รับชำระค่ายกลังที่สถานี ไม่เกิน 50 บาทต่อกล่อง"),
    ("parcel", "พัสดุส่งถึงที่", K.PARCEL, "ส่งวันจันทร์ ถึง ศุกร์ กรุงเทพฯ และปริมณฑลรับของวันถัดไป"),
]


class Command(BaseCommand):
    help = "Seed shipping methods that the shop offers today."

    def handle(self, *args, **opts):
        for i, (code, name, kind, desc) in enumerate(METHODS):
            ShippingMethod.objects.update_or_create(
                code=code, defaults={"name": name, "kind": kind, "description": desc, "sort_order": i})
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(METHODS)} shipping methods."))
