#!/usr/bin/env bash
set -euo pipefail

tool="${1:?Usage: smoke.sh FORENSIC_TOOL}"
script="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)/scripts/collect-evidence.sh"
temporary="$(mktemp -d "./.forensics-smoke.XXXXXX")"
trap 'rm -rf -- "$temporary"' EXIT
mkdir -- "$temporary/evidence"
printf 'sample evidence\n' >"$temporary/evidence/event.log"

hash_line="$("$tool" hash "$temporary/evidence/event.log")"
[[ $hash_line == *"event.log"* ]]
"$tool" inspect "$temporary/evidence/event.log" | grep -q '"sha256"'
FORENSIC_TOOL="$tool" "$script" "$temporary/evidence" "$temporary/manifest.json" "SMOKE-1" "Local Tester"
grep -q '"caseId": "SMOKE-1"' "$temporary/manifest.json"
grep -q '"event.log"' "$temporary/manifest.json"

printf 'forensics smoke checks passed\n'
