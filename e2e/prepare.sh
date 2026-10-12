#!/bin/sh
# Starts the API on a fresh e2e database: migrations, seeded catalog, test staff, then the server.
# Playwright runs this as the API web server, so the database is ready before anything calls it.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/../apps/api"
DB="$HERE/e2e.sqlite3"
export DATABASE_URL="sqlite:///$DB" PROMPTPAY_ID=0812345678 RATE_LIMIT_ENABLED=0 DJANGO_DEBUG=1
rm -f "$DB"
uv run python manage.py migrate --noinput >/dev/null
uv run python manage.py seed_catalog >/dev/null
uv run python manage.py seed_shipping >/dev/null
uv run python manage.py seed_inventory >/dev/null
uv run python manage.py shell < "$HERE/setup_db.py"
exec uv run python manage.py runserver localhost:8000
