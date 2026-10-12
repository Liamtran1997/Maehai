"""Products as they appear on the old site (https://www.maehai.com), read on 12/10/2026.

Names, the rubber-band colour in brackets, and the photos. The site shows no prices, no descriptions and no weights:
those come from the shop owner. Slugs reuse the seeded catalog where the product already exists.
"""
IMG = "https://itp1.itopfile.com/ImageServer/cf6b210751f01cff/0/0/{}"

# (name on site, slug, category slug, subtitle, bands, photo file names on the site)
PRODUCTS = [
    ("หมูยอพริกไทยดำ (ยางเหลือง)", "moo-yo-black-pepper", "moo-yo", "ยางเหลือง", ["yellow"],
     ["iTopPlus1284444869207.webp", "iTopPlus277355392249.webp"]),
    ("หมูยอขนาดเล็ก กลาง ใหญ่", "moo-yo-sizes", "moo-yo", "", [], ["iTopPlus1130584859456.webp"]),
    ("หมูยอแผ่น", "moo-yo-sheet", "moo-yo", "", [], ["iTopPlus744673448996.webp"]),
    ("หมูยอหนังหมู (ยางแดง)", "moo-yo-pork-skin", "moo-yo", "ยางแดง", ["red"],
     ["iTopPlus418357399833.webp", "iTopPlus974100347559.webp"]),
    ("หมูยอเห็ดหอม (ยางเขียว)", "moo-yo-shiitake", "moo-yo", "ยางเขียว", ["green"],
     ["iTopPlus116629116074.webp", "iTopPlus1257424967509.webp"]),
    ("หมูยอทรงเครื่อง (ยางเหลืองและเขียว)", "moo-yo-mixed", "moo-yo", "ยางเหลืองและเขียว", ["yellow", "green"],
     ["iTopPlus1137136990822.webp", "iTopPlus517004219875.webp"]),
    ("หมูยอพริก (ยางเหลืองและแดง)", "moo-yo-chili", "moo-yo", "ยางเหลืองและแดง", ["yellow", "red"],
     ["iTopPlus1425141363124.webp", "iTopPlus1417713416327.webp"]),
    ("แหนมหมู", "naem-pork", "naem", "ห่อใบตอง", [], ["iTopPlus1201212580478.webp"]),
    ("แหนมหมูใบมะยม", "naem-makrut-leaf", "naem", "ห่อใบตอง", [], ["iTopPlus1154217202029.webp"]),
    ("แหนมซี่โครงอ่อน", "naem-ribs", "naem", "ห่อใบตอง", [], ["iTopPlus1165490427706.webp"]),
    ("ไส้กรอกอีสานเนื้อ", "isan-sausage-beef", "isan-sausage", "", [], ["iTopPlus816528691812.webp"]),
    ("ไส้กรอกอีสานหมู", "isan-sausage-pork", "isan-sausage", "", [], ["iTopPlus700597904135.webp"]),
    ("ไส้กรอกอีสาน", "isan-sausage-classic", "isan-sausage", "", [], ["iTopPlus77947347175.webp"]),
    ("ชุดก๋วยจั๊บเส้นสด", "kuay-chap-set-fresh", "noodles", "", [],
     ["%E0%B8%8A%E0%B8%B8%E0%B8%94%E0%B8%81%E0%B9%8B%E0%B8%A7%E0%B8%A2%E0%B8%88%E0%B8%B1%E0%B9%8A%E0%B8%9A%E0%B9%80%E0%B8%AA%E0%B9%89%E0%B8%99%E0%B8%AA%E0%B8%94z-z160511776513.webp"]),
    ("ชุดก๋วยจั๊บเส้นแห้ง", "kuay-chap-set-dry", "noodles", "", [],
     ["%E0%B8%8A%E0%B8%B8%E0%B8%94%E0%B8%81%E0%B9%8B%E0%B8%A7%E0%B8%A2%E0%B8%88%E0%B8%B1%E0%B9%8A%E0%B8%9A%E0%B9%80%E0%B8%AA%E0%B9%89%E0%B8%99%E0%B9%81%E0%B8%AB%E0%B9%89%E0%B8%87z-z869828575724.webp"]),
    ("เส้นก๋วยจั๊บญวน (สด)", "fresh-kuay-chap-noodles", "noodles", "", [], ["iTopPlus1386637709733.webp"]),
    ("หอมเจียว", "fried-shallot", "fried-aromatics", "", [], ["iTopPlus808916701371.webp"]),
    ("กระเทียมเจียว", "fried-garlic", "fried-aromatics", "", [], ["iTopPlus537000421767.webp"]),
    ("หมูสวรรค์", "moo-sawan", "dried-pork", "", [], ["iTopPlus1338991176831.webp"]),
    ("หมูหยอง", "moo-yong", "dried-pork", "", [], ["iTopPlus159822370351.webp"]),
    ("หมูฝอย", "moo-foi", "dried-pork", "", [], ["iTopPlus1208216944072.webp"]),
    ("แคบหมู", "pork-rind", "pork-rind", "", [], ["iTopPlus286925455062.webp"]),
    ("แคบหมูสมุนไพร", "pork-rind-herbal", "pork-rind", "", [], ["iTopPlus1365896846782.webp"]),
    ("หมูกระจก", "moo-krajok", "dried-pork", "", [], ["iTopPlus1375931539068.webp"]),
    ("กุนเชียงหมู", "kun-chiang-pork", "chinese-sausage", "", [], ["iTopPlus1296167483641.webp"]),
    ("กุนเชียงไก่", "kun-chiang-chicken", "chinese-sausage", "", [], ["iTopPlus600735013066.webp"]),
    ("กุนเชียงปลา", "kun-chiang-fish", "chinese-sausage", "", [], ["iTopPlus1113975373758.webp"]),
    ("ก้อยข้าวปุ้น", "koi-khao-poon", "other", "", [], ["%E0%B8%81%E0%B9%89%E0%B8%AD%E0%B8%A2%E0%B8%82%E0%B9%89%E0%B8%B2%E0%B8%A7%E0%B8%9B%E0%B8%B8%E0%B9%89%E0%B8%99z-z980158700906.webp"]),
]

# Categories the import needs beyond the seeded ones.
EXTRA_CATEGORIES = [("other", "อาหารอื่นๆ")]
