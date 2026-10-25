#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d)"
port="${PAYROLL_SMOKE_PORT:-18983}"
export PAYROLL_DATABASE="$tmp/payroll.sqlite"
export PAYROLL_ADMIN_TOKEN="smoke-admin-token-0123456789abcdef"
export PAYROLL_REVIEWER_TOKEN="smoke-review-token-0123456789abcdef"
php -S "127.0.0.1:$port" -t "$root/public" "$root/public/index.php" >"$tmp/server.log" 2>&1 &
server_pid=$!
cleanup() { kill "$server_pid" 2>/dev/null || true; wait "$server_pid" 2>/dev/null || true; rm -rf "$tmp"; }
trap cleanup EXIT

for _ in $(seq 1 40); do
  if curl --silent --fail "http://127.0.0.1:$port/health" >/dev/null; then break; fi
  sleep 0.25
done
curl --silent --fail -X POST "http://127.0.0.1:$port/employees" -H "Authorization: Bearer $PAYROLL_ADMIN_TOKEN" -H 'Content-Type: application/json' --data '{"employee_code":"EMP-7","display_name":"=Formula Check","monthly_gross_cents":345678,"fixed_deduction_cents":45678}' >"$tmp/created.json"
curl --silent --fail -X POST "http://127.0.0.1:$port/payroll/runs" -H "Authorization: Bearer $PAYROLL_ADMIN_TOKEN" -H 'Content-Type: application/json' --data '{"period":"2026-10"}' >"$tmp/run.json"
curl --silent --fail "http://127.0.0.1:$port/payroll/export/2026-10.csv" -H "Authorization: Bearer $PAYROLL_REVIEWER_TOKEN" >"$tmp/export.csv"
curl --silent --fail "http://127.0.0.1:$port/audit" -H "Authorization: Bearer $PAYROLL_ADMIN_TOKEN" >"$tmp/audit.json"
if curl --silent --output /dev/null --write-out '%{http_code}' -X POST "http://127.0.0.1:$port/employees" -H "Authorization: Bearer $PAYROLL_REVIEWER_TOKEN" -H 'Content-Type: application/json' --data '{}' | grep -q '^201$'; then
  echo 'reviewer role unexpectedly created employee' >&2
  exit 1
fi
grep -Fq "'=Formula Check" "$tmp/export.csv"
grep -Fq '300000' "$tmp/run.json"
echo 'payroll HTTP, RBAC, calculation, export, and audit smoke passed'
