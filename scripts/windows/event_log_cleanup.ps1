<#
.SYNOPSIS
    Clear old Windows event logs.
.DESCRIPTION
    Clears event logs older than the specified number of days from
    Application, System, Security, and Setup logs. Older entries are
    exported to a backup file before removal.
.SUPPORTS
    Windows (Windows 10/11, Windows Server 2016+)
.REQUIRES
    Administrator privileges
.ESTIMATE
    1-3 minutes
.ROLLBACK
    Backups are saved to $env:SYSTEMROOT\Logs\EventLogBackups\.
#>

param(
    [int]$OlderThanDays = 30,
    [string]$BackupRoot = "$env:SYSTEMROOT\Logs\EventLogBackups"
)

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

    $logNames = @('Application', 'System', 'Security', 'Setup')

    # Create backup directory
    if (-not (Test-Path $BackupRoot)) {
        New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
    }

    $cutoff = (Get-Date).AddDays(-$OlderThanDays)

    foreach ($logName in $logNames) {
        try {
            Write-Log "Processing log: $logName"

            # Check if log exists and has entries
            $log = Get-WinEvent -ListLog $logName -ErrorAction SilentlyContinue
            if (-not $log -or $log.RecordCount -eq 0) {
                Write-Log "Log '$logName' is empty or unavailable. Skipping." 'WARN'
                continue
            }

            $backupFile = Join-Path -Path $BackupRoot -ChildPath "${logName}_${cutoff:yyyyMMdd}.evtx"
            Write-Log "Backing up $logName to $backupFile ..."
            wevtutil epl "$logName" "$backupFile" /q:"*[System[TimeCreated[timediff(@SystemTime) >= $((Get-Date $cutoff).ToFileTimeUtc())]]]" 2>$null

            Write-Log "Clearing log: $logName"
            wevtutil cl "$logName" /q:"*[System[TimeCreated[timediff(@SystemTime) < $((Get-Date $cutoff).ToFileTimeUtc())]]]" 2>$null

            Write-Log "$logName cleared (entries older than $OlderThanDays days backed up)."
        } catch {
            Write-Log "Failed to process $logName : $_" 'WARN'
        }
    }

    Write-Log "Event log cleanup complete. Backups stored in: $BackupRoot"
    exit 0
}
catch {
    Write-Log $_.Exception.Message 'ERROR'
    exit 1
}
