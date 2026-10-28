#!/bin/sh
set -eu
umask 077
cd /opt/guild-seekers
backup_dir=/var/backups/guild-seekers
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
stamp=$(date -u +%Y%m%d-%H%M%S)
temporary="$backup_dir/guild-$stamp.dump.partial"
trap 'rm -f "$temporary"' EXIT
docker compose -f compose.yaml -f compose.production.yaml exec -T db pg_dump -U guild -d guild -Fc > "$temporary"
test -s "$temporary"
mv "$temporary" "$backup_dir/guild-$stamp.dump"
find "$backup_dir" -maxdepth 1 -type f -name 'guild-*.dump' -mtime +7 -delete
echo "Backup saved: $backup_dir/guild-$stamp.dump"
