#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DUMP_DIR="$PROJECT_DIR/dump"

if docker compose version >/dev/null 2>&1; then
	DC=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
	DC=(docker-compose)
else
	echo "Error: neither 'docker compose' nor 'docker-compose' is available."
	exit 1
fi

cd "$PROJECT_DIR"
mkdir -p "$DUMP_DIR"

TS=$(date +%Y%m%d_%H%M%S)
DB_FILE="${1:-$DUMP_DIR/odoo_backup_${TS}.dump}"
FS_FILE="${DB_FILE%.dump}_filestore.tar.gz"

echo "Starting db container..."
"${DC[@]}" up -d db

echo "Exporting database to: $DB_FILE"
"${DC[@]}" exec -T db pg_dump -U odoo -d postgres -Fc > "$DB_FILE"

echo "Exporting filestore to: $FS_FILE"
"${DC[@]}" run --rm -v odoo-web-data:/filestore alpine tar czf - -C /filestore . > "$FS_FILE"

echo "Done. Backup files:"
echo "  DB:        $DB_FILE"
echo "  Filestore: $FS_FILE"