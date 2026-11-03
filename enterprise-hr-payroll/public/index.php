<?php
declare(strict_types=1);

use Portfolio\Payroll\PayrollStore;

require dirname(__DIR__) . '/vendor/autoload.php';

header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');

function respond(int $status, mixed $body, string $type = 'application/json; charset=utf-8'): never
{
    http_response_code($status);
    header('Content-Type: ' . $type);
    if ($type === 'text/csv; charset=utf-8') echo $body;
    else echo json_encode($body, JSON_THROW_ON_ERROR | JSON_INVALID_UTF8_SUBSTITUTE);
    exit;
}

function jsonBody(): array
{
    $length = (int)($_SERVER['CONTENT_LENGTH'] ?? 0);
    if ($length > 16384) respond(413, ['error' => 'request body exceeds 16 KiB']);
    $raw = file_get_contents('php://input', false, null, 0, 16385);
    if (!is_string($raw) || strlen($raw) > 16384) respond(413, ['error' => 'request body exceeds 16 KiB']);
    try { $body = json_decode($raw, true, 32, JSON_THROW_ON_ERROR); }
    catch (JsonException) { respond(400, ['error' => 'request body must be valid JSON']); }
    if (!is_array($body) || array_is_list($body)) respond(400, ['error' => 'request body must be a JSON object']);
    return $body;
}

function actorRole(): string
{
    $header = $_SERVER['HTTP_AUTHORIZATION'] ?? '';
    if (!preg_match('/^Bearer ([A-Za-z0-9._~-]{32,256})$/D', $header, $match)) respond(401, ['error' => 'bearer token required']);
    $token = $match[1];
    $admin = getenv('PAYROLL_ADMIN_TOKEN') ?: '';
    $reviewer = getenv('PAYROLL_REVIEWER_TOKEN') ?: '';
    if ($admin !== '' && hash_equals($admin, $token)) return 'admin';
    if ($reviewer !== '' && hash_equals($reviewer, $token)) return 'reviewer';
    respond(401, ['error' => 'invalid bearer token']);
}

function requireRole(string $actual, string ...$allowed): void
{
    if (!in_array($actual, $allowed, true)) respond(403, ['error' => 'role does not allow this action']);
}

function csvCell(string $value): string
{
    if (preg_match('/^[\s]*[=+\-@]/u', $value)) $value = "'" . $value;
    return '"' . str_replace('"', '""', $value) . '"';
}

try {
    $databasePath = getenv('PAYROLL_DATABASE') ?: dirname(__DIR__) . '/data/payroll.sqlite';
    $directory = dirname($databasePath);
    if (!is_dir($directory) && !mkdir($directory, 0700, true) && !is_dir($directory)) throw new RuntimeException('cannot create private database directory');
    $db = new PDO('sqlite:' . $databasePath, options: [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
    if (DIRECTORY_SEPARATOR !== '\\') chmod($directory, 0700);
    if (DIRECTORY_SEPARATOR !== '\\' && file_exists($databasePath)) chmod($databasePath, 0600);
    $store = new PayrollStore($db);

    $method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
    $path = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH);
    if ($method === 'GET' && $path === '/health') respond(200, ['status' => 'ok']);
    $role = actorRole();

    if ($method === 'GET' && $path === '/employees') {
        requireRole($role, 'admin', 'reviewer'); respond(200, ['employees' => $store->employees()]);
    }
    if ($method === 'POST' && $path === '/employees') {
        requireRole($role, 'admin'); $body = jsonBody();
        foreach (['employee_code', 'display_name', 'monthly_gross_cents', 'fixed_deduction_cents'] as $field) if (!array_key_exists($field, $body)) respond(400, ['error' => "missing field: $field"]);
        if (!is_string($body['employee_code']) || !is_string($body['display_name']) || !is_int($body['monthly_gross_cents']) || !is_int($body['fixed_deduction_cents'])) respond(400, ['error' => 'employee fields have invalid types']);
        $id = $store->addEmployee($body['employee_code'], $body['display_name'], $body['monthly_gross_cents'], $body['fixed_deduction_cents'], $role);
        respond(201, ['id' => $id]);
    }
    if ($method === 'POST' && $path === '/payroll/runs') {
        requireRole($role, 'admin'); $body = jsonBody();
        if (!is_string($body['period'] ?? null)) respond(400, ['error' => 'period must be a YYYY-MM string']);
        respond(201, ['runs' => $store->runPayroll($body['period'], $role)]);
    }
    if ($method === 'GET' && preg_match('#^/payroll/runs/((?:20|21)[0-9]{2}-(?:0[1-9]|1[0-2]))$#D', (string)$path)) {
        requireRole($role, 'admin', 'reviewer');
        $period = basename((string)$path);
        respond(200, ['runs' => $store->payroll($period)]);
    }
    if ($method === 'GET' && preg_match('#^/payroll/export/((?:20|21)[0-9]{2}-(?:0[1-9]|1[0-2]))\.csv$#D', (string)$path)) {
        requireRole($role, 'admin', 'reviewer');
        $period = basename((string)$path, '.csv');
        $stream = fopen('php://temp', 'w+b');
        fputcsv($stream, ['period', 'employee_code', 'display_name', 'gross_cents', 'fixed_deduction_cents', 'net_cents']);
        foreach ($store->payroll($period) as $row) {
            fputcsv($stream, [$period, csvCell((string)$row['employee_code']), csvCell((string)$row['display_name']), (int)$row['gross_cents'], (int)$row['deduction_cents'], (int)$row['net_cents']], ',', '"', '\\');
        }
        rewind($stream); $csv = stream_get_contents($stream); fclose($stream);
        respond(200, $csv, 'text/csv; charset=utf-8');
    }
    if ($method === 'GET' && $path === '/audit') {
        requireRole($role, 'admin'); respond(200, ['events' => $store->auditEvents()]);
    }
    respond(404, ['error' => 'not found']);
} catch (PDOException $error) {
    if (str_contains($error->getMessage(), 'UNIQUE constraint failed')) respond(409, ['error' => 'record conflicts with existing data']);
    error_log('payroll database request failed: ' . $error->getCode());
    respond(500, ['error' => 'database request failed']);
} catch (RuntimeException $error) {
    if (str_contains($error->getMessage(), 'already exists')) respond(409, ['error' => $error->getMessage()]);
    respond(400, ['error' => $error->getMessage()]);
} catch (Throwable $error) {
    error_log('payroll request failed: ' . get_class($error));
    respond(500, ['error' => 'internal request failure']);
}
