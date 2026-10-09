<#
.SYNOPSIS
    Manages the RomM WSL2 distro: install, start, stop, open, status, logs, uninstall.

.EXAMPLE
    .\RomM.ps1 install -Rootfs .\romm-wsl.tar.gz -Library 'D:\Games\ROMs'
    .\RomM.ps1 start
    .\RomM.ps1 upgrade -Rootfs .\romm-wsl-new.tar.gz
#>
param(
    [Parameter(Position = 0, Mandatory = $true)]
    [ValidateSet('install', 'start', 'stop', 'restart', 'open', 'status', 'logs', 'upgrade', 'uninstall')]
    [string]$Command,

    [string]$Rootfs,
    [string]$Library,
    [int]$Port = 8080,
    [switch]$KeepData
)

$ErrorActionPreference = 'Stop'
# Windows PowerShell 5.1 leaves $PSScriptRoot empty in param() defaults.
if (-not $Rootfs) { $Rootfs = Join-Path $PSScriptRoot 'romm-wsl.tar.gz' }
$Distro = 'RomM'
$DataDir = Join-Path $env:LOCALAPPDATA 'RomM'
$SettingsFile = Join-Path $DataDir 'romm.env'

# Windows PowerShell 5.1 turns a native command's stderr into a terminating
# error under 'Stop', so wsl.exe runs with 'Continue' and callers check $LASTEXITCODE.
function Invoke-Wsl([string[]]$WslArgs) {
    $ErrorActionPreference = 'Continue'
    & wsl.exe @WslArgs
}

function Test-Distro {
    # wsl.exe writes UTF-16 to a redirected stdout.
    $prev = [Console]::OutputEncoding
    [Console]::OutputEncoding = [Text.Encoding]::Unicode
    try { $names = Invoke-Wsl @('--list', '--quiet') 2>$null } finally { [Console]::OutputEncoding = $prev }
    return [bool]($names | Where-Object { $_.Trim() -eq $Distro })
}

function Test-Running {
    if (-not (Test-Distro)) { return $false }
    Invoke-Wsl @('-d', $Distro, '-u', 'root', '--', '/usr/local/bin/romm-wsl', '--running') 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}

function Get-Port {
    if (Test-Path $SettingsFile) {
        $line = Get-Content $SettingsFile | Where-Object { $_ -match '^ROMM_PORT=(\d+)' } | Select-Object -First 1
        if ($line) { return [int]$Matches[1] }
    }
    return 8080
}

function Wait-Http([int]$port, [int]$seconds = 180) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 "http://localhost:$port/api/heartbeat" | Out-Null
            return $true
        } catch { Start-Sleep -Seconds 2 }
    }
    return $false
}

function Install-RomM {
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
        throw 'WSL is not available. Run "wsl --install --no-distribution" as administrator, reboot, then retry.'
    }
    Invoke-Wsl @('--status') *> $null
    if ($LASTEXITCODE -ne 0) {
        throw 'WSL is not set up. Run "wsl --install --no-distribution" as administrator, reboot, then retry.'
    }
    if (Test-Distro) { throw "A WSL distro named $Distro already exists. Use '.\RomM.ps1 upgrade' instead." }
    if (-not (Test-Path $Rootfs)) { throw "Rootfs not found: $Rootfs" }
    if ($Library -and -not (Test-Path $Library -PathType Container)) { throw "Library folder not found: $Library" }

    New-Item -ItemType Directory -Force -Path (Join-Path $DataDir 'wsl') | Out-Null
    Write-Host "Importing $Distro distro (this takes a minute)..."
    Invoke-Wsl @('--import', $Distro, (Join-Path $DataDir 'wsl'), $Rootfs, '--version', '2')
    if ($LASTEXITCODE -ne 0) { throw 'wsl --import failed' }
    Restore-State

    if (-not (Test-Path $SettingsFile)) {
        @(
            '# RomM settings. Restart RomM after editing (.\RomM.ps1 restart).'
            '# Any variable from https://docs.romm.app/latest/Getting-Started/Environment-Variables/ works here.'
            "ROMM_LIBRARY_PATH='$Library'"
            "ROMM_PORT=$Port"
            'SCAN_WORKERS=4'
            'WEB_SERVER_CONCURRENCY=2'
            'HASHEOUS_API_ENABLED=true'
            '# SCREENSCRAPER_USER='
            '# SCREENSCRAPER_PASSWORD='
            '# RETROACHIEVEMENTS_API_KEY='
            '# STEAMGRIDDB_API_KEY='
        ) | Set-Content -Encoding ascii $SettingsFile
    }
    Write-Host "Installed. Settings: $SettingsFile"
}

function Start-RomM {
    if (-not (Test-Distro)) { throw "$Distro is not installed. Run '.\RomM.ps1 install' first." }
    if (Test-Running) { Write-Host 'RomM is already running.'; return }
    # wsl.exe must stay attached for the lifetime of RomM, or WSL idles the distro out.
    Start-Process -WindowStyle Hidden -FilePath wsl.exe `
        -ArgumentList @('-d', $Distro, '-u', 'root', '--', '/usr/local/bin/romm-wsl', "`"$SettingsFile`"")
    $port = Get-Port
    Write-Host "Starting RomM on http://localhost:$port ..."
    if (Wait-Http $port) { Write-Host 'RomM is up.' }
    else { Write-Warning "RomM did not answer yet. Check '.\RomM.ps1 logs'." }
}

function Stop-RomM {
    if (-not (Test-Running)) { Write-Host 'RomM is not running.'; return }
    Write-Host 'Stopping RomM...'
    Invoke-Wsl @('-d', $Distro, '-u', 'root', '--', '/usr/local/bin/romm-wsl', '--stop')
    Invoke-Wsl @('--terminate', $Distro) | Out-Null
    Write-Host 'Stopped.'
}

# Everything RomM writes lives inside the distro, so it is carried across a re-import.
$StatePaths = @('romm', 'var/lib/mysql', 'redis-data', 'etc/romm/secrets.env')
$Backup = Join-Path $DataDir 'state-backup.tar'

function Get-WslPath([string]$path) {
    return (Invoke-Wsl @('-d', $Distro, '-u', 'root', '--', 'wslpath', '-u', $path)).Trim()
}

function Backup-State {
    Write-Host "Backing up RomM data to $Backup ..."
    Invoke-Wsl (@('-d', $Distro, '-u', 'root', '--', 'tar', '-C', '/', '--exclude=romm/library', '-cf', (Get-WslPath $Backup)) + $StatePaths)
    if ($LASTEXITCODE -ne 0) { throw "Backup failed, $Distro was left as is." }
    Invoke-Wsl @('--terminate', $Distro) | Out-Null
}

function Restore-State {
    if (-not (Test-Path $Backup)) { return }
    Write-Host 'Restoring RomM data...'
    Invoke-Wsl @('-d', $Distro, '-u', 'root', '--', 'tar', '-C', '/', '-xpf', (Get-WslPath $Backup))
    if ($LASTEXITCODE -ne 0) { throw "Restore failed. Your data is still in $Backup." }
    Invoke-Wsl @('--terminate', $Distro) | Out-Null
    Remove-Item $Backup
}

function Uninstall-RomM {
    if (Test-Distro) {
        Stop-RomM
        if ($KeepData) { Backup-State }
        Invoke-Wsl @('--unregister', $Distro) | Out-Null
    }
    if (-not $KeepData) { Remove-Item -Recurse -Force $DataDir -ErrorAction SilentlyContinue }
}

function Update-RomM {
    if (-not (Test-Path $Rootfs)) { throw "Rootfs not found: $Rootfs" }
    $wasRunning = Test-Running
    $script:KeepData = $true
    Uninstall-RomM
    Install-RomM
    Write-Host 'Upgraded.'
    if ($wasRunning) { Start-RomM }
}

switch ($Command) {
    'install' { Install-RomM }
    'start' { Start-RomM }
    'stop' { Stop-RomM }
    'restart' { Stop-RomM; Start-RomM }
    'open' {
        if (-not (Test-Running)) { Start-RomM }
        Start-Process "http://localhost:$(Get-Port)"
    }
    'status' {
        if (Test-Running) { Write-Host "Running on http://localhost:$(Get-Port)" } else { Write-Host 'Stopped' }
    }
    'upgrade' { Update-RomM }
    'logs' { Invoke-Wsl @('-d', $Distro, '-u', 'root', '--', 'tail', '-n', '200', '-f', '/var/log/romm/romm.log') }
    'uninstall' {
        Uninstall-RomM
        if ($KeepData) { Write-Host "Uninstalled. Your RomM data is kept in $DataDir and is restored on the next install." }
        else { Write-Host 'Uninstalled. Your library folder was not touched.' }
    }
}
