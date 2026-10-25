[CmdletBinding()]
param(
    [ValidateSet('Json', 'Csv')][string]$Format = 'Json',
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\src\ConfigAudit.psm1') -Force
$results = Invoke-ComplianceScan -Snapshot (Get-LocalSnapshot)

if ($OutputPath) {
    if ($Format -eq 'Csv') { $results | Export-Csv -LiteralPath $OutputPath -NoTypeInformation }
    else { $results | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $OutputPath -Encoding utf8 }
} elseif ($Format -eq 'Csv') {
    $results | ConvertTo-Csv -NoTypeInformation
} else {
    $results | ConvertTo-Json -Depth 4
}
