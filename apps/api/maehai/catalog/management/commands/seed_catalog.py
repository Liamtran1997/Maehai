"""Seed the catalog with the products listed on the old maehai.com.

PRICES AND WEIGHTS ARE SAMPLE VALUES. The old site shows no prices. Replace them in the back office
before going live. Safe to re-run: existing products are updated by slug, nothing is deleted.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from maehai.catalog.models import Category, Product, ProductVariant

SIZES = [("เล็ก", 6000), ("กลาง", 8500), ("ใหญ่", 15000)]

# (slug, name, category slug, subtitle, bands, badge, [(label, price_satang)] or None for a single "ปกติ" size)
CATEGORIES = [
    ("moo-yo", "หมูยอ"), ("naem", "แหนม"), ("isan-sausage", "ไส้กรอกอีสาน"),
    ("noodles", "เส้นก๋วยจั๊บญวน"), ("fried-aromatics", "หอมเจียว กระเทียมเจียว"),
    ("dried-pork", "หมูหยอง หมูฝอย หมูสวรรค์"), ("pork-rind", "แคบหมู"), ("chinese-sausage", "กุนเชียง"),
]

PRODUCTS = [
    ("moo-yo-black-pepper", "หมูยอพริกไทยดำ", "moo-yo", "ยางเหลือง", ["yellow"], "best_seller", SIZES, 6500),
    ("moo-yo-sheet", "หมูยอแผ่น", "moo-yo", "", [], "", None, 7500),
    ("moo-yo-pork-skin", "หมูยอหนังหมู", "moo-yo", "ยางแดง", ["red"], "", SIZES, 8000),
    ("moo-yo-shiitake", "หมูยอเห็ดหอม", "moo-yo", "ยางเขียว", ["green"], "", SIZES, 9000),
    ("moo-yo-mixed", "หมูยอทรงเครื่อง", "moo-yo", "ยางเหลืองและเขียว", ["yellow", "green"], "", SIZES, 9000),
    ("moo-yo-chili", "หมูยอพริก", "moo-yo", "ยางเหลืองและแดง", ["yellow", "red"], "", SIZES, 8500),
    ("naem-pork", "แหนมหมู", "naem", "ห่อใบตอง", [], "", None, 6000),
    ("naem-makrut-leaf", "แหนมหมูใบมะยม", "naem", "ห่อใบตอง", [], "", None, 6500),
    ("naem-ribs", "แหนมซี่โครงอ่อน", "naem", "ห่อใบตอง", [], "", None, 9500),
    ("isan-sausage-beef", "ไส้กรอกอีสานเนื้อ", "isan-sausage", "", [], "", None, 8000),
    ("isan-sausage-pork", "ไส้กรอกอีสานหมู", "isan-sausage", "", [], "", None, 7000),
    ("isan-sausage-classic", "ไส้กรอกอีสาน", "isan-sausage", "", [], "", None, 7000),
    ("fresh-kuay-chap-noodles", "เส้นก๋วยจั๊บญวน (สด)", "noodles", "", [], "", None, 4000),
    ("fried-shallot", "หอมเจียว", "fried-aromatics", "", [], "", None, 5000),
    ("fried-garlic", "กระเทียมเจียว", "fried-aromatics", "", [], "", None, 5000),
    ("moo-sawan", "หมูสวรรค์", "dried-pork", "", [], "", None, 12000),
    ("moo-yong", "หมูหยอง", "dried-pork", "", [], "", None, 9000),
    ("moo-foi", "หมูฝอย", "dried-pork", "", [], "", None, 9000),
    ("pork-rind", "แคบหมู", "pork-rind", "", [], "", None, 6000),
    ("pork-rind-herbal", "แคบหมูสมุนไพร", "pork-rind", "", [], "", None, 6500),
    ("moo-krajok", "หมูกระจก", "dried-pork", "", [], "", None, 11000),
    ("kun-chiang-pork", "กุนเชียงหมู", "chinese-sausage", "", [], "", None, 10000),
]


class Command(BaseCommand):
    help = "Seed categories and products from the old site (sample prices)."

    @transaction.atomic
    def handle(self, *args, **opts):
        cats = {}
        for i, (slug, name) in enumerate(CATEGORIES):
            cats[slug], _ = Category.objects.update_or_create(slug=slug, defaults={"name": name, "sort_order": i})

        for i, (slug, name, cat, subtitle, bands, badge, sizes, single_price) in enumerate(PRODUCTS):
            product, _ = Product.objects.update_or_create(
                slug=slug,
                defaults={"name": name, "category": cats[cat], "subtitle": subtitle, "bands": bands,
                          "badge": badge, "sort_order": i,
                          "description": "ผลิตสดใหม่ทุกวัน จากวัตถุดิบคัดสรรจากฟาร์มคุณภาพ"},
            )
            variants = sizes or [("ปกติ", single_price)]
            for j, (label, price) in enumerate(variants):
                ProductVariant.objects.update_or_create(
                    sku=f"{slug}-{j + 1}",
                    defaults={"product": product, "label": label, "price_satang": price, "sort_order": j},
                )
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(PRODUCTS)} products."))
        self.stdout.write(self.style.WARNING("Prices are SAMPLE values. Update them in the back office before launch."))
