"""URLs the browser must be able to open. Behind Docker the API sees its own internal host, so the public origin is configured."""
from django.conf import settings


def public_file_url(request, file_field) -> str | None:
    """Absolute URL of an uploaded file as customers see it: PUBLIC_MEDIA_ORIGIN when set (production), else this request's host."""
    if not file_field:
        return None
    if settings.PUBLIC_MEDIA_ORIGIN:
        return f"{settings.PUBLIC_MEDIA_ORIGIN}{file_field.url}"
    return request.build_absolute_uri(file_field.url)
