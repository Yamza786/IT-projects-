# Enterprise HR and Payroll Prototype

A small PHP 8.2+ and SQLite service for employee records, fixed monthly payroll calculations, role-separated access, immutable audit events, and CSV export. Amounts are stored as integer cents.

## Setup

Install PHP with PDO SQLite and mbstring, Composer, then:

```sh
composer install
export PAYROLL_ADMIN_TOKEN='use-a-long-random-secret-at-least-32-chars'
export PAYROLL_REVIEWER_TOKEN='use-a-different-long-random-secret'
php -S 127.0.0.1:8080 -t public
```

The API requires a bearer token for all employee/payroll/audit routes. Admin can create employees and calculate payroll; reviewer can view/export. The health endpoint is unauthenticated. Example calls and payloads are in the API list below.

| Method | Path | Role | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | Public | Process health |
| `GET` | `/employees` | Admin, reviewer | List active employee records |
| `POST` | `/employees` | Admin | Add code, display name, monthly gross cents, fixed deduction cents |
| `POST` | `/payroll/runs` | Admin | Calculate a period such as `2026-10`, once only |
| `GET` | `/payroll/runs/2026-10` | Admin, reviewer | View payroll calculations |
| `GET` | `/payroll/export/2026-10.csv` | Admin, reviewer | CSV export with spreadsheet formula escaping |
| `GET` | `/audit` | Admin | View recent append-only audit events |

Example employee JSON: `{"employee_code":"EMP-1","display_name":"Avery Example","monthly_gross_cents":500000,"fixed_deduction_cents":25000}`. Payroll computes `net = gross - fixed deduction` using integer cents and stores the actor, period, and result in the audit trail. Duplicate runs are rejected and the complete calculation rolls back if one row fails.

## Verification

`composer test` exercises integer-cent calculations, audit records, duplicate-run rollback, amount validation and period validation. `bash scripts/smoke.sh` drives the local HTTP service and checks role denial and formula-safe CSV output. CI runs PHPUnit and this integration smoke.

## Important limits

This is not a compliant production payroll engine. It has no tax, statutory deductions, benefits, leave, proration, bank payment, employee self-service, legal jurisdiction rules, or double-entry accounting. Fixed deductions are demo inputs only. Employee names and compensation are sensitive: keep the local database private, use distinct high-entropy tokens, TLS and managed secret storage in a deployment, backups with access controls, and a jurisdiction-specific payroll/security review. The built-in PHP server is for local development only.
