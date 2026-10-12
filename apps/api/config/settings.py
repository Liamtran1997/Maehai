import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-secret")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

DOMAIN_APPS = [
    "maehai.core",
    "maehai.catalog",
    "maehai.inventory",
    "maehai.orders",
    "maehai.payments",
    "maehai.shipping",
    "maehai.customers",
    "maehai.reports",
    "maehai.cms",
    "maehai.notifications",
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "ninja",
    *DOMAIN_APPS,
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": dj_database_url.config(
    default=os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}"))}

LANGUAGE_CODE = "th"
TIME_ZONE = "Asia/Bangkok"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = [o for o in os.environ.get(
    "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",") if o]

# Thailand / money
CURRENCY = "THB"
VAT_ENABLED = os.environ.get("VAT_ENABLED", "0") == "1"
VAT_RATE_PERCENT = int(os.environ.get("VAT_RATE", "7"))
PROMPTPAY_ID = os.environ.get("PROMPTPAY_ID", "")

# Cookie auth across the shop/admin origins (admin SPA calls the API with credentials)
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

# Ordering rules (Thailand, fresh food)
ORDER_CUTOFF_HOUR = 13            # orders placed after 13:00 count as the next day
NO_FULFILLMENT_WEEKDAYS = [6]     # Python weekday(): Monday=0 ... Sunday=6
NON_WORKING_DATES = [d for d in os.environ.get("NON_WORKING_DATES", "").split(",") if d]  # YYYY-MM-DD, Thai public holidays
PAYMENT_WINDOW_MINUTES = 15       # PromptPay QR lifetime
PUBLIC_SHOP_URL = os.environ.get("PUBLIC_SHOP_URL", "http://localhost:3000")

# Slip verification: dotted path of a class with verify(payment) -> SlipResult. ManualReview = staff check by hand.
SLIP_VERIFIER = os.environ.get("SLIP_VERIFIER", "maehai.payments.providers.ManualReview")
SLIP_MAX_BYTES = 5 * 1024 * 1024

# LINE Official Account (Messaging API). LINE Notify was shut down in 2025, so everything goes through the OA.
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
LINE_OA_ID = os.environ.get("LINE_OA_ID", "@maehai")              # basic ID, used to build the "link my order" button
LINE_STAFF_IDS = [i for i in os.environ.get("LINE_STAFF_IDS", "").split(",") if i]  # user or group IDs that get staff alerts
LINE_CLIENT = os.environ.get("LINE_CLIENT", "maehai.notifications.line.LineClient")
ADMIN_URL = os.environ.get("ADMIN_URL", "http://localhost:5173")
NOTIFY_MAX_ATTEMPTS = 5

# Rate limiting. Counters live in the Django cache: use Redis in production so every worker shares them.
CACHES = {
    "default": (
        {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": os.environ["REDIS_URL"]}
        if os.environ.get("REDIS_URL")
        else {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    )
}
RATE_LIMIT_ENABLED = os.environ.get("RATE_LIMIT_ENABLED", "1") == "1"
# How many reverse proxies sit in front of the API (nginx, a load balancer...). 0 = trust only the socket address.
# With N > 0 the client IP is taken from X-Forwarded-For N entries from the right, which a client cannot forge.
TRUSTED_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", "0"))
# name: (max requests, window seconds). Windows are fixed, so a client can burst up to 2x at a window edge.
RATE_LIMITS = {
    "order_create_ip": (10, 3600),
    "order_create_phone": (10, 86400),
    "lookup_ip": (20, 600),
    "lookup_fail_ip": (10, 900),
    "lookup_fail_order": (5, 900),
    "token_fail_ip": (20, 900),
    "login_fail_ip": (10, 900),
    "login_fail_user": (5, 900),
    "charge_order": (20, 3600),
    "slip_order": (10, 3600),
    "slip_ip": (30, 3600),
}

# Inventory
DEFAULT_FULFILLMENT_BRANCH = os.environ.get("DEFAULT_FULFILLMENT_BRANCH", "srinarong")  # ships delivery orders unless it is out of stock
LOW_STOCK_THRESHOLD = int(os.environ.get("LOW_STOCK_THRESHOLD", "5"))
ORDER_UNPAID_EXPIRY_HOURS = int(os.environ.get("ORDER_UNPAID_EXPIRY_HOURS", "24"))  # unpaid orders release their stock after this long
