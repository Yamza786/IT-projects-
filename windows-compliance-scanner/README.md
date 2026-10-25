# Windows Configuration and Compliance Scanner

A PowerShell 7, read-only snapshot scanner for a small set of local security settings: UAC, Windows Update policy, Microsoft Defender real-time protection, system-drive BitLocker protection, and Domain/Private/Public firewall profiles.

```powershell
pwsh -File scripts/scan.ps1
pwsh -File scripts/scan.ps1 -Format Csv -OutputPath .\compliance-report.csv
Invoke-Pester -Path tests
```

Each rule returns `pass`, `fail`, or `unknown` with observed state, expected state and remediation guidance. Missing or inaccessible data is reported as unknown; the scanner never treats unavailable evidence as a pass. Reports omit hostnames and user identities by design.

## Safety and scope

The scanner only reads registry values and system status providers. It does not modify settings, install updates, enable security features, or run suggested remediations. Recommendations are guidance for an administrator to review. Policy paths and available cmdlets vary across Windows editions and management policies; unknown results need manual verification. This small catalog is not a certification or full enterprise baseline, and its CSV/JSON output may still reveal security posture, so store reports privately.

Pester tests feed explicit snapshots to the pure evaluation function. Windows CI runs those tests and a read-only scan smoke.
