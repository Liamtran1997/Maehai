"""Small copies of product photos for the shop's grids and category tiles.

The photos are 800 px wide and phones show them about 175 px wide, so the full file is mostly wasted bytes there.
The copy is 400 px wide WebP, stored next to the photo (same storage), and served by the same /media/products path.
"""
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

THUMB_WIDTH = 400


def make_thumb(photo) -> None:
    """Fills photo.thumb (a ProductImage) from photo.image and saves it. Does nothing if the file cannot be read:
    the shop then falls back to the full photo."""
    try:
        with photo.image.open("rb") as f, Image.open(f) as im:
            im = ImageOps.exif_transpose(im)
            im.thumbnail((THUMB_WIDTH, THUMB_WIDTH * 4), Image.Resampling.LANCZOS)   # keeps the aspect ratio, never enlarges
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGBA" if "transparency" in im.info else "RGB")
            out = BytesIO()
            im.save(out, "WEBP", quality=80, method=4)
    except (OSError, UnidentifiedImageError, ValueError):
        return
    photo.thumb.save("thumb.webp", ContentFile(out.getvalue()), save=False)   # upload_to gives it its own random name
    type(photo).objects.filter(pk=photo.pk).update(thumb=photo.thumb.name)
