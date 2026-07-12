<#
.SYNOPSIS
    Restart IIS with application pool recycling.
.DESCRIPTION
    Stops and starts the W3SVC service, then recycles all application pools.
.SUPPORTS
    Windows (Windows 10/11, Windows Server 2016+ with IIS)
.REQUIRES
    Administrator privileges, IIS module installed
.ESTIMATE
    10-30 seconds
.ROLLBACK
    Re-run script to restart IIS; app pools will be re-created from config.
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

    # Stop IIS
    Write-Log "Stopping W3SVC service..."
    Stop-Service W3SVC -Force -ErrorAction Stop
    Write-Log "W3SVC stopped."

    # Start IIS
    Write-Log "Starting W3SVC service..."
    Start-Service W3SVC -ErrorAction Stop
    Write-Log "W3SVC started."

    # Verify service status
    $svc = Get-Service W3SVC
    if ($svc.Status -ne 'Running') {
        throw "W3SVC service is not running after restart."
    }
    Write-Log "W3SVC is running."

    # Recycle app pools using WebAdministration module
    if (Get-Module -ListAvailable -Name WebAdministration) {
        Import-Module WebAdministration -Force -ErrorAction Stop
        $pools = Get-ChildItem IIS:\AppPools | Select-Object -ExpandProperty Name
        foreach ($pool in $pools) {
            Write-Log "Recycling app pool: $pool"
            Restart-WebAppPool -Name $pool -ErrorAction SilentlyContinue
        }
        Write-Log "All application pools recycled."
    } else {
        Write-Log "WebAdministration module not found; skipping app pool recycling." 'WARN'
    }

    exit 0
}
catch {
    Write-Log $_.Exception.Message 'ERROR'
    exit 1
}
