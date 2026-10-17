#!/bin/sh
set -eu
umask 077
: "${ENTERPRISE_ADMIN_KEY:?Set ENTERPRISE_ADMIN_KEY in the shell before running backup}"
base_url=${ENTERPRISE_URL:-http://127.0.0.1:8000}
destination=${1:-./backups}
mkdir -p "$destination"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
target="$destination/polymath-enterprise-$stamp.json"
temporary="$target.partial"
trap 'rm -f "$temporary"' EXIT HUP INT TERM
curl --fail --silent --show-error --max-time 30 \
  -H "X-API-Key: $ENTERPRISE_ADMIN_KEY" \
  "$base_url/api/backup" -o "$temporary"
python3 -c 'import json,sys; d=json.load(open(sys.argv[1],encoding="utf-8")); assert d.get("format")=="polymath-enterprise-backup-v1"' "$temporary"
mv "$temporary" "$target"
trap - EXIT HUP INT TERM
printf 'Verified backup: %s\n' "$target"
