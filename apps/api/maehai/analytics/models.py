from django.db import models


class WebEvent(models.Model):
    """One thing a visitor did in the shop, recorded only after they agreed to it. No name, phone, address, order number,
    IP or full URL is ever stored here; `visitor` is a random id the browser made after consent."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    visitor = models.CharField(max_length=32, db_index=True)
    kind = models.CharField(max_length=20)
    path = models.CharField(max_length=120, blank=True)
    slug = models.CharField(max_length=120, blank=True, help_text="Product slug for product events")
    name = models.CharField(max_length=40, blank=True, help_text="Web vital name or search words")
    # Web vitals are milliseconds, except CLS which has no unit and is stored times 1000.
    value = models.FloatField(null=True, blank=True, help_text="Web vital value, search result count, or cart value in satang")
    qty = models.PositiveSmallIntegerField(null=True, blank=True)
    device = models.CharField(max_length=10, blank=True)
    source = models.CharField(max_length=40, blank=True)
    design_version = models.CharField(max_length=40, blank=True)

    class Meta:
        indexes = [models.Index(fields=["kind", "created_at"])]


class WebPageCount(models.Model):
    """Page views per day and kind of page. A bare counter: no id, no session. Only filled when the owner has turned on
    counting without consent (ANALYTICS_COUNT_WITHOUT_CONSENT) after legal advice."""

    date = models.DateField()
    page_type = models.CharField(max_length=20)
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["date", "page_type"], name="webpagecount_unique")]


class ConsentCount(models.Model):
    """How many times the consent banner was answered each way, per day. Used for the consent rate; no id."""

    date = models.DateField()
    choice = models.CharField(max_length=5)   # allow | deny
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["date", "choice"], name="consentcount_unique")]
