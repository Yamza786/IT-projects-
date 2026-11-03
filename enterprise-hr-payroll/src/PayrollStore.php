<?php
declare(strict_types=1);

namespace Portfolio\Payroll;

use PDO;
use PDOException;
use RuntimeException;

final class PayrollStore
{
    public function __construct(private readonly PDO $db)
    {
        $this->db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $this->db->exec('PRAGMA foreign_keys = ON');
        $this->db->exec('PRAGMA busy_timeout = 5000');
        $this->db->exec('CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY,
            employee_code TEXT NOT NULL UNIQUE CHECK(length(employee_code) BETWEEN 1 AND 32),
            display_name TEXT NOT NULL CHECK(length(trim(display_name)) BETWEEN 1 AND 120),
            monthly_gross_cents INTEGER NOT NULL CHECK(monthly_gross_cents BETWEEN 1 AND 100000000000),
            fixed_deduction_cents INTEGER NOT NULL CHECK(fixed_deduction_cents BETWEEN 0 AND monthly_gross_cents),
            active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )');
        $this->db->exec("CREATE TABLE IF NOT EXISTS payroll_runs (
            id INTEGER PRIMARY KEY,
            period TEXT NOT NULL CHECK(period GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
            employee_id INTEGER NOT NULL REFERENCES employees(id),
            gross_cents INTEGER NOT NULL,
            deduction_cents INTEGER NOT NULL,
            net_cents INTEGER NOT NULL,
            calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            calculated_by TEXT NOT NULL,
            UNIQUE(period, employee_id)
        )");
        $this->db->exec('CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            record_type TEXT NOT NULL,
            record_id INTEGER NOT NULL,
            occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            details_json TEXT NOT NULL
        )');
    }

    /** @return int employee row id */
    public function addEmployee(string $code, string $name, int $grossCents, int $deductionCents, string $actor): int
    {
        $code = trim($code); $name = trim($name);
        if ($code === '' || strlen($code) > 32 || !preg_match('/^[A-Za-z0-9._-]+$/', $code)) throw new RuntimeException('Employee code must use 1–32 letters, digits, dot, underscore, or dash');
        if ($name === '' || mb_strlen($name) > 120) throw new RuntimeException('Employee name must contain 1–120 characters');
        if ($grossCents < 1 || $grossCents > 100_000_000_000 || $deductionCents < 0 || $deductionCents > $grossCents) throw new RuntimeException('Payroll amounts are outside the accepted range');
        $this->db->beginTransaction();
        try {
            $statement = $this->db->prepare('INSERT INTO employees(employee_code,display_name,monthly_gross_cents,fixed_deduction_cents) VALUES(?,?,?,?)');
            $statement->execute([$code, $name, $grossCents, $deductionCents]);
            $id = (int)$this->db->lastInsertId();
            $this->audit($actor, 'employee.created', 'employee', $id, ['employee_code' => $code]);
            $this->db->commit();
            return $id;
        } catch (\Throwable $error) {
            if ($this->db->inTransaction()) $this->db->rollBack();
            throw $error;
        }
    }

    /** @return list<array<string,mixed>> */
    public function employees(): array
    {
        return $this->db->query('SELECT id,employee_code,display_name,monthly_gross_cents,fixed_deduction_cents,active FROM employees ORDER BY employee_code')->fetchAll(PDO::FETCH_ASSOC);
    }

    /** @return list<array<string,mixed>> */
    public function runPayroll(string $period, string $actor): array
    {
        if (!preg_match('/^(20[0-9]{2}|21[0-9]{2})-(0[1-9]|1[0-2])$/', $period)) throw new RuntimeException('Payroll period must be YYYY-MM between 2000-01 and 2199-12');
        $this->db->beginTransaction();
        try {
            $employees = $this->db->query('SELECT id,employee_code,monthly_gross_cents,fixed_deduction_cents FROM employees WHERE active=1 ORDER BY employee_code')->fetchAll(PDO::FETCH_ASSOC);
            if (count($employees) === 0) throw new RuntimeException('No active employees to process');
            $insert = $this->db->prepare('INSERT INTO payroll_runs(period,employee_id,gross_cents,deduction_cents,net_cents,calculated_by) VALUES(?,?,?,?,?,?)');
            $results = [];
            foreach ($employees as $employee) {
                $gross = (int)$employee['monthly_gross_cents']; $deduction = (int)$employee['fixed_deduction_cents'];
                $insert->execute([$period, $employee['id'], $gross, $deduction, $gross - $deduction, $actor]);
                $id = (int)$this->db->lastInsertId();
                $this->audit($actor, 'payroll.calculated', 'payroll_run', $id, ['period' => $period, 'employee_code' => $employee['employee_code']]);
                $results[] = ['id' => $id, 'period' => $period, 'employee_code' => $employee['employee_code'], 'gross_cents' => $gross, 'deduction_cents' => $deduction, 'net_cents' => $gross - $deduction];
            }
            $this->db->commit();
            return $results;
        } catch (\Throwable $error) {
            if ($this->db->inTransaction()) $this->db->rollBack();
            if ($error instanceof PDOException && str_contains($error->getMessage(), 'UNIQUE constraint failed')) throw new RuntimeException('Payroll already exists for this period; duplicate runs are blocked');
            throw $error;
        }
    }

    /** @return list<array<string,mixed>> */
    public function payroll(string $period): array
    {
        $query = $this->db->prepare('SELECT r.id,r.period,e.employee_code,e.display_name,r.gross_cents,r.deduction_cents,r.net_cents,r.calculated_at,r.calculated_by FROM payroll_runs r JOIN employees e ON e.id=r.employee_id WHERE r.period=? ORDER BY e.employee_code');
        $query->execute([$period]);
        return $query->fetchAll(PDO::FETCH_ASSOC);
    }

    /** @return list<array<string,mixed>> */
    public function auditEvents(int $limit = 100): array
    {
        $statement = $this->db->prepare('SELECT actor,action,record_type,record_id,occurred_at,details_json FROM audit_events ORDER BY id DESC LIMIT ?');
        $statement->bindValue(1, max(1, min($limit, 500)), PDO::PARAM_INT);
        $statement->execute();
        return $statement->fetchAll(PDO::FETCH_ASSOC);
    }

    /** @param array<string,mixed> $details */
    private function audit(string $actor, string $action, string $type, int $id, array $details): void
    {
        $insert = $this->db->prepare('INSERT INTO audit_events(actor,action,record_type,record_id,details_json) VALUES(?,?,?,?,?)');
        $insert->execute([$actor, $action, $type, $id, json_encode($details, JSON_THROW_ON_ERROR)]);
    }
}
