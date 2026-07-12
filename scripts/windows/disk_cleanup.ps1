<#
.SYNOPSIS
    Windows disk cleanup utility.
.DESCRIPTION
    Runs the built-in Cleanmgr.exe with an appropriate cleanup profile
    (sageset / sagerun) and optionally empties the Recycle Bin.
.SUPPORTS
    Windows (Windows 10/11, Windows Server 2016+)
.REQUIRES
    Administrator privileges
.ESTIMATE
    5-15 minutes
.ROLLBACK
    N/A (destructive); deleted files cannot be recovered.
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

    # Configure a Disk Cleanup profile (SageSet: 1)
    # This enables: Temporary files, Recycle Bin, Delivery Optimization, etc.
    $regPath = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\VolumeCaches'
    if (-not (Test-Path "$regPath\Temporary Files")) {
        Write-Log "VolumeCaches registry key not found; running Cleanmgr with defaults." 'WARN'
    }

    # Save the cleanup settings using sageset:1
    Write-Log "Configuring disk cleanup profile (sageset:1)..."
    Start-Process -FilePath "$env:SYSTEMROOT\System32\cleanmgr.exe" -ArgumentList '/sageset:1' -Wait -NoNewWindow
    Write-Log "Please ensure you have selected the desired cleanup categories in the dialog."

    # Run the cleanup using sagerun:1
    Write-Log "Running disk cleanup (sagerun:1)..."
    Start-Process -FilePath "$env:SYSTEMROOT\System32\cleanmgr.exe" -ArgumentList '/sagerun:1' -Wait -NoNewWindow

    # Empty Recycle Bin (prompt)
    $answer = Read-Host "Empty Recycle Bin? [y/N] "
    if ($answer -match '^[Yy]') {
        Write-Log "Emptying Recycle Bin..."
        Clear-RecycleBin -Force -ErrorAction SilentlyContinue
        Write-Log "Recycle Bin emptied."
    }

    # Report disk space
    $drive = Get-PSDrive -Name C | Select-Object Used, Free
    $freeGB = [math]::Round($drive.Free / 1GB, 2)
    Write-Log "Disk C: free space: ${freeGB} GB"

    exit 0
}
catch {
    Write-Log $_.Exception.Message 'ERROR'
    exit 1
}
