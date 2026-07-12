<#
.SYNOPSIS
    Clean Temporary files and folders.
.DESCRIPTION
    Removes files from %TEMP%, %WINDIR%\Temp, and user temp locations
    older than 24 hours.
.SUPPORTS
    Windows (Windows 10/11, Windows Server 2016+)
.REQUIRES
    Administrator privileges
.ESTIMATE
    1-5 minutes
.ROLLBACK
    N/A (destructive); deleted temp files cannot be recovered.
#>

param(
    [int]$AgeHours = 24
)

$ErrorActionPreference = 'Stop'
$VerbosePreference = 'Continue'

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

    $tempPaths = @(
        "$env:TEMP",
        "$env:WINDIR\Temp",
        "$env:LOCALAPPDATA\Temp"
    ) | Where-Object { Test-Path $_ }

    $cutoff = (Get-Date).AddHours(-$AgeHours)
    $totalSize = 0
    $totalFiles = 0

    foreach ($path in $tempPaths) {
        Write-Log "Scanning $path ..."
        $items = Get-ChildItem -Path $path -Recurse -Force -ErrorAction SilentlyContinue |
            Where-Object { $_.LastWriteTime -lt $cutoff -or $_.CreationTime -lt $cutoff }

        foreach ($item in $items) {
            try {
                if ($item.PSIsContainer) {
                    Remove-Item -LiteralPath $item.FullName -Recurse -Force -ErrorAction SilentlyContinue
                } else {
                    $totalSize += $item.Length
                    Remove-Item -LiteralPath $item.FullName -Force -ErrorAction SilentlyContinue
                    $totalFiles++
                }
            } catch {
                Write-Log "Failed to remove $($item.FullName): $_" 'WARN'
            }
        }
    }

    $sizeMB = [math]::Round($totalSize / 1MB, 2)
    Write-Log "Cleaned $totalFiles files / $sizeMB MB from temp directories."
    exit 0
}
catch {
    Write-Log $_.Exception.Message 'ERROR'
    exit 1
}
