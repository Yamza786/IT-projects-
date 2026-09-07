#!/bin/bash
# Simple backup script
# Usage: ./backup.sh /path/to/source /path/to/dest

set -euo pipefail

SRC="$1"
DEST_DIR="$2"

TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
BASENAME=$(basename "${SRC%/}")
DEST="${DEST_DIR}/${BASENAME}-${TIMESTAMP}.tar.gz"

mkdir -p "${DEST_DIR}"

tar -czf "${DEST}" -C "$(dirname "$SRC")" "$BASENAME"

echo "Backup saved to: ${DEST}"
