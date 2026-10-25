Set-StrictMode -Version Latest

function Invoke-ComplianceScan {
    [CmdletBinding()]
    param([Parameter(Mandatory)][hashtable]$Snapshot)

    $checks = [System.Collections.Generic.List[object]]::new()
    $rules = @(
        @{ Id = 'uac'; Name = 'User Account Control'; Key = 'UacEnabled'; Expected = $true; Guidance = 'Keep User Account Control enabled.' },
        @{ Id = 'windows_update'; Name = 'Automatic Windows Update'; Key = 'WindowsUpdateAutomatic'; Expected = $true; Guidance = 'Configure managed automatic security updates.' },
        @{ Id = 'defender_realtime'; Name = 'Microsoft Defender real-time protection'; Key = 'DefenderRealtime'; Expected = $true; Guidance = 'Review Microsoft Defender protection and policy.' },
        @{ Id = 'bitlocker'; Name = 'System drive encryption'; Key = 'BitLockerProtected'; Expected = $true; Guidance = 'Enable and verify protection for the operating-system drive.' }
    )
    foreach ($rule in $rules) {
        $value = $Snapshot[$rule.Key]
        $status = if ($null -eq $value) { 'unknown' } elseif ($value -eq $rule.Expected) { 'pass' } else { 'fail' }
        $checks.Add([pscustomobject]@{ id = $rule.Id; name = $rule.Name; status = $status; observed = $value; expected = $rule.Expected; guidance = $rule.Guidance })
    }

    $profiles = $Snapshot['FirewallProfiles']
    foreach ($profileName in @('Domain', 'Private', 'Public')) {
        $value = if ($null -eq $profiles) { $null } else { $profiles[$profileName] }
        $status = if ($null -eq $value) { 'unknown' } elseif ($value -eq $true) { 'pass' } else { 'fail' }
        $checks.Add([pscustomobject]@{ id = "firewall_$($profileName.ToLowerInvariant())"; name = "$profileName firewall profile"; status = $status; observed = $value; expected = $true; guidance = "Enable the $profileName firewall profile." })
    }
    return $checks.ToArray()
}

function Get-LocalSnapshot {
    [CmdletBinding()]
    param()

    $uac = $null
    try { $uac = (Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System' -Name EnableLUA -ErrorAction Stop).EnableLUA -eq 1 } catch { }

    $automaticUpdates = $null
    try {
        $policy = Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU' -Name NoAutoUpdate -ErrorAction Stop
        $automaticUpdates = $policy.NoAutoUpdate -eq 0
    } catch { }

    $defender = $null
    try { $defender = [bool](Get-MpComputerStatus -ErrorAction Stop).RealTimeProtectionEnabled } catch { }

    $bitLocker = $null
    try {
        $volume = Get-BitLockerVolume -MountPoint $env:SystemDrive -ErrorAction Stop
        $bitLocker = ($volume.ProtectionStatus -eq 'On' -and $volume.VolumeStatus -eq 'FullyEncrypted')
    } catch { }

    $profiles = @{}
    try {
        foreach ($profile in Get-NetFirewallProfile -ErrorAction Stop) { $profiles[[string]$profile.Name] = [bool]$profile.Enabled }
    } catch { $profiles = $null }

    return @{
        UacEnabled = $uac
        WindowsUpdateAutomatic = $automaticUpdates
        DefenderRealtime = $defender
        BitLockerProtected = $bitLocker
        FirewallProfiles = $profiles
    }
}

Export-ModuleMember -Function Invoke-ComplianceScan, Get-LocalSnapshot
