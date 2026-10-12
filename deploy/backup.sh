#!/usr/bin/env bash
# Back up the database and uploaded files (product photos and payment slips).
# Usage (from the repo root):  deploy/backup.sh [keep_days]     Run daily from cron, e.g.:
#   15 3 * * *  cd /srv/maehai && deploy/backup.sh 14 >> deploy/backups/backup.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
KEEP_DAYS="${1:-14}"
DIR="deploy/backups"; STAMP="$(date +%Y%m%d-%H%M%S)"
COMPOSE=(docker compose -f deploy/docker-compose.yml --env-file deploy/.env)
mkdir -p "$DIR"; umask 077

echo "[$STAMP] dumping database"
"${COMPOSE[@]}" exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' > "$DIR/db-$STAMP.dump"
echo "[$STAMP] archiving uploads"
"${COMPOSE[@]}" exec -T api tar -C /data/media -czf - . > "$DIR/media-$STAMP.tar.gz"

# A zero-size file means the dump failed silently: fail loudly instead.
for f in "$DIR/db-$STAMP.dump" "$DIR/media-$STAMP.tar.gz"; do [ -s "$f" ] || { echo "empty backup: $f" >&2; exit 1; }; done
find "$DIR" -type f \( -name 'db-*.dump' -o -name 'media-*.tar.gz' \) -mtime +"$KEEP_DAYS" -delete
echo "[$STAMP] done: $(ls -1 "$DIR" | wc -l) files kept"
