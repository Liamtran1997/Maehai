from django.core.management.base import BaseCommand

from maehai.catalog.models import ProductImage
from maehai.catalog.thumbs import make_thumb


class Command(BaseCommand):
    help = "Makes the small copy of every product photo that does not have one yet. Safe to run again."

    def handle(self, *args, **options):
        made = skipped = 0
        for photo in ProductImage.objects.filter(thumb="").exclude(image=""):
            make_thumb(photo)
            photo.refresh_from_db(fields=["thumb"])
            if photo.thumb:
                made += 1
            else:
                skipped += 1
                self.stderr.write(f"could not read photo {photo.pk}: {photo.image.name}")
        self.stdout.write(self.style.SUCCESS(f"small copies made: {made}" + (f", unreadable: {skipped}" if skipped else "")))
