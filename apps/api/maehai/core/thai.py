from datetime import date

THAI_MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]


def thai_date(d: date) -> str:
    """12 ต.ค. 2569 (Buddhist era)."""
    return f"{d.day} {THAI_MONTHS[d.month - 1]} {d.year + 543}"
