<#
.SYNOPSIS
    Restart critical Windows services.
.DESCRIPTION
    Restarts a curated list of critical infrastructure services:
    DHCP Client, DNS Client, Windows Event Log, Remote Procedure Call,
    Windows Time, and Windows Management Instrumentation.
.SUPPORTS
    Windows (Windows 10/11, Windows Server 2016+)
.REQUIRES
    Administrator privileges
.ESTIMATE
    10-30 seconds
.ROLLBACK
    Re-run script to restart same services; original state is not preserved.
#>

$ErrorActionPreference = 'Stop'

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line = "[$timestamp] [$Level] $Message"
    if ($Level -eq 'ERROR') { Write-Host $line -ForegroundColor Red }
    elseif ($Level -eq 'WARN') { Write-Host $line -ForegroundColor Yellow }
    else { Write-Host $line }
}

function Assert-Administrator {
    $identity = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not $identity.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "This script must be run as Administrator."
    }
}

try {
    Assert-Administrator

    $criticalServices = @(
        @{ Name = 'Dhcp'; Display = 'DHCP Client' },
        @{ Name = 'Dnscache'; Display = 'DNS Client' },
        @{ Name = 'EventLog'; Display = 'Windows Event Log' },
        @{ Name = 'RpcSs'; Display = 'Remote Procedure Call (RPC)' },
        @{ Name = 'W32Time'; Display = 'Windows Time' },
        @{ Name = 'Winmgmt'; Display = 'Windows Management Instrumentation' }
    )

    foreach ($svc in $criticalServices) {
        try {
            Write-Log "Restarting $($svc.Display)..."
            Restart-Service -Name $svc.Name -Force -ErrorAction Stop
            Write-Log "$($svc.Display) restarted successfully."
        } catch {
            Write-Log "Failed to restart $($svc.Display): $_" 'WARN'
        }
    }

    Write-Log "All critical services processed."
    exit 0
}
catch {
    Write-Log $_.Exception.Message 'ERROR'
    exit 1
}
