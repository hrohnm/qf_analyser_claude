#!/bin/bash
# DB Backup nach einem Datenload
# Usage: ./backup_db.sh
mkdir -p backups
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILE="backups/qf_analyser_${TIMESTAMP}.pgdump"
docker compose exec -T db pg_dump -U qf_user -d qf_analyser --format=custom > "$FILE"
echo "Backup gespeichert: $FILE ($(du -sh "$FILE" | cut -f1))"
