BeforeAll {
    Import-Module (Join-Path $PSScriptRoot '..\src\ConfigAudit.psm1') -Force
}

Describe 'Invoke-ComplianceScan' {
    It 'marks an explicitly compliant snapshot as pass' {
        $snapshot = @{
            UacEnabled = $true
            WindowsUpdateAutomatic = $true
            DefenderRealtime = $true
            BitLockerProtected = $true
            FirewallProfiles = @{ Domain = $true; Private = $true; Public = $true }
        }
        $results = Invoke-ComplianceScan -Snapshot $snapshot
        $results.Count | Should -Be 7
        @($results | Where-Object status -ne 'pass').Count | Should -Be 0
    }

    It 'fails disabled controls and reports missing provider data as unknown' {
        $snapshot = @{
            UacEnabled = $false
            WindowsUpdateAutomatic = $null
            DefenderRealtime = $true
            BitLockerProtected = $false
            FirewallProfiles = @{ Domain = $true; Private = $false }
        }
        $results = Invoke-ComplianceScan -Snapshot $snapshot
        ($results | Where-Object id -eq 'uac').status | Should -Be 'fail'
        ($results | Where-Object id -eq 'windows_update').status | Should -Be 'unknown'
        ($results | Where-Object id -eq 'bitlocker').status | Should -Be 'fail'
        ($results | Where-Object id -eq 'firewall_private').status | Should -Be 'fail'
        ($results | Where-Object id -eq 'firewall_public').status | Should -Be 'unknown'
    }

    It 'returns recommendations without running remediation' {
        $result = Invoke-ComplianceScan -Snapshot @{ UacEnabled = $false; FirewallProfiles = @{} } | Where-Object id -eq 'uac'
        $result.guidance | Should -Be 'Keep User Account Control enabled.'
        $result.PSObject.Properties.Name | Should -Contain 'observed'
    }
}
