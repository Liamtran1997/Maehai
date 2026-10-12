"""Where uploaded files live. Chosen by STORAGE_BACKEND in .env (see config/settings.py).

Two kinds of files:
  products  product photos. Public: the shop shows them to everyone.
  private   payment slips. Never public, in both backends. Served only through a staff-only API endpoint.
"""
import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage, storages


class PrivateFileSystemStorage(FileSystemStorage):
    """Local storage outside MEDIA_ROOT, so no web server rule can ever expose it. Read settings on each use so
    test overrides apply."""

    @property
    def base_location(self) -> str:
        return str(settings.PRIVATE_MEDIA_ROOT)

    @property
    def location(self) -> str:
        return os.path.abspath(self.base_location)


def product_storage():
    return storages["products"]


def private_storage():
    return storages["private"]
