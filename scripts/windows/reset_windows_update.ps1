<#
.SYNOPSIS
    Reset Windows Update components.
.DESCRIPTION
    Stops Windows Update services, clears the SoftwareDistribution and
    Catroot2 folders, reregisters update DLLs, and restarts services.
.SUPPORTS
    Windows (Windows 10/11, Windows Server 2016+)
.REQUIRES
    Administrator privileges
.ESTIMATE
    2-5 minutes
.ROLLBACK
    SoftwareDistribution and Catroot2 are backed up before removal.
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

    $backupDir = "$env:SYSTEMROOT\SoftwareDistribution.backup.$(Get-Date -Format 'yyyyMMddHHmmss')"
    $catrootBackup = "$env:SYSTEMROOT\System32\Catroot2.backup.$(Get-Date -Format 'yyyyMMddHHmmss')"

    $services = @('wuauserv', 'bits', 'cryptsvc', 'trustedinstaller')

    # Stop services
    foreach ($svc in $services) {
        Write-Log "Stopping service: $svc"
        Stop-Service -Name $svc -Force -ErrorAction SilentlyContinue
    }

    # Backup and clear SoftwareDistribution
    $sdPath = "$env:SYSTEMROOT\SoftwareDistribution"
    if (Test-Path $sdPath) {
        Write-Log "Backing up SoftwareDistribution to $backupDir"
        Move-Item -LiteralPath $sdPath -Destination $backupDir -Force
    }

    # Backup and clear Catroot2
    $catPath = "$env:SYSTEMROOT\System32\Catroot2"
    if (Test-Path $catPath) {
        Write-Log "Backing up Catroot2 to $catrootBackup"
        Move-Item -LiteralPath $catPath -Destination $catrootBackup -Force
    }

    # Re-register update DLLs
    $dlls = @(
        'msxml3.dll', 'qmgr.dll', 'qmgrprxy.dll',
        'wuapi.dll', 'wuaueng.dll', 'wucltui.dll',
        'wups.dll', 'wups2.dll'
    )
    $sysDir = "$env:SYSTEMROOT\System32"
    foreach ($dll in $dlls) {
        $path = Join-Path -Path $sysDir -ChildPath $dll
        if (Test-Path $path) {
            Write-Log "Re-registering: $dll"
            & regsvr32.exe /s "$path"
        }
    }

    # Reset Winsock
    Write-Log "Resetting Winsock..."
    & netsh winsock reset
    & netsh winhttp reset proxy

    # Start services
    foreach ($svc in $services) {
        Write-Log "Starting service: $svc"
        Start-Service -Name $svc -ErrorAction SilentlyContinue
    }

    Write-Log "Windows Update components reset complete. A reboot is recommended."
    exit 0
}
catch {
    Write-Log $_.Exception.Message 'ERROR'
    exit 1
}
