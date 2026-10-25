#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf 'Usage: %s EVIDENCE_DIR MANIFEST_FILE CASE_ID EXAMINER\n' "$0" >&2
}

if [[ $# -ne 4 || ! -d $1 ]]; then
  usage
  exit 2
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
tool="${FORENSIC_TOOL:-$script_dir/../build/forensic-tool}"
if [[ ! -x $tool ]]; then
  printf 'forensic-tool executable not found: %s\n' "$tool" >&2
  exit 1
fi

exec "$tool" manifest --root "$1" --out "$2" --case "$3" --examiner "$4"
