<?php
declare(strict_types=1);

namespace Portfolio\Payroll\Tests;

use PDO;
use PHPUnit\Framework\TestCase;
use Portfolio\Payroll\PayrollStore;
use RuntimeException;

final class PayrollStoreTest extends TestCase
{
    private PDO $db;
    private PayrollStore $store;

    protected function setUp(): void
    {
        $this->db = new PDO('sqlite::memory:');
        $this->store = new PayrollStore($this->db);
    }

    public function testPayrollUsesIntegerCentsAndAuditsCalculations(): void
    {
        $this->store->addEmployee('EMP-001', 'Avery Example', 520001, 10001, 'admin');
        $results = $this->store->runPayroll('2026-10', 'admin');
        self::assertSame(520001, $results[0]['gross_cents']);
        self::assertSame(10001, $results[0]['deduction_cents']);
        self::assertSame(510000, $results[0]['net_cents']);
        self::assertCount(1, $this->store->payroll('2026-10'));
        self::assertCount(2, $this->store->auditEvents());
    }

    public function testDuplicatePeriodRollsBackAllNewRows(): void
    {
        $this->store->addEmployee('EMP-1', 'One', 120000, 0, 'admin');
        $this->store->addEmployee('EMP-2', 'Two', 240000, 10000, 'admin');
        $this->store->runPayroll('2026-10', 'admin');
        try {
            $this->store->runPayroll('2026-10', 'admin');
            self::fail('A duplicate period must be rejected');
        } catch (RuntimeException $error) {
            self::assertStringContainsString('already exists', $error->getMessage());
        }
        self::assertCount(2, $this->store->payroll('2026-10'));
        self::assertCount(4, $this->store->auditEvents());
    }

    public function testRejectsInvalidDatesAndAmounts(): void
    {
        $this->expectException(RuntimeException::class);
        $this->store->addEmployee('EMP-1', 'Invalid', 1000, 1001, 'admin');
    }

    public function testRejectsInvalidPayrollPeriod(): void
    {
        $this->expectException(RuntimeException::class);
        $this->store->runPayroll('2026-13', 'admin');
    }
}
