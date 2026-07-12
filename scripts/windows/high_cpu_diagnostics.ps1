<#
.SYNOPSIS
    Diagnose high CPU usage processes.
.DESCRIPTION
    Lists top CPU-consuming processes with detailed information including
    PID, process name, CPU time, memory usage, and start time.
    Optionally generates a performance trace for deeper analysis.
.SUPPORTS
    Windows (Windows 10/11, Windows Server 2016+)
.REQUIRES
    Administrative privileges (for performance trace)
.ESTIMATE
    30 seconds - 2 minutes
.ROLLBACK
    N/A (read-only diagnostic; no system changes are made).
#>

param(
    [int]$TopCount = 10,
    [switch]$GenerateTrace
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

try {
    Write-Log "Gathering top ${TopCount} CPU-consuming processes..."

    $processes = Get-Process | Where-Object { $_.CPU -gt 0 } |
        Sort-Object CPU -Descending |
        Select-Object -First $TopCount

    if (-not $processes) {
        Write-Log "No processes with measurable CPU time found." 'WARN'
        exit 0
    }

    $results = $processes | Select-Object @{N='PID';E={$_.Id}},
        @{N='ProcessName';E={$_.ProcessName}},
        @{N='CPU(s)';E={[math]::Round($_.CPU, 2)}},
        @{N='WorkingSet(MB)';E={[math]::Round($_.WorkingSet64 / 1MB, 2)}},
        @{N='StartTime';E={$_.StartTime}}

    $results | Format-Table -AutoSize | Out-Host

    # Optionally generate a performance trace
    if ($GenerateTrace) {
        $traceFile = "$env:TEMP\cpu_diag_$(Get-Date -Format 'yyyyMMddHHmmss').etl"
        Write-Log "Starting 30-second performance trace to $traceFile ..."
        try {
            logman start "CPU_Diag" -o $traceFile -pf "$env:SYSTEMROOT\System32\perf_windows.xml" -ets -si 1 -max 256 -ErrorAction Stop
            Write-Log "Tracing for 30 seconds..."
            Start-Sleep -Seconds 30
            logman stop "CPU_Diag" -ets -ErrorAction Stop
            Write-Log "Performance trace saved: $traceFile"
        } catch {
            Write-Log "Performance trace failed: $_" 'WARN'
        }
    }

    Write-Log "CPU diagnostics complete."
    exit 0
}
catch {
    Write-Log $_.Exception.Message 'ERROR'
    exit 1
}
