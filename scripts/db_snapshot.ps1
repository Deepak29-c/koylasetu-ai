# Save or bring back the whole demo state of the Docker setup: the database and the files
# volume (uploaded originals and page images), so a demo does not wait on OCR.
#
#   powershell -ExecutionPolicy Bypass -File scripts\db_snapshot.ps1 create [name]
#   powershell -ExecutionPolicy Bypass -File scripts\db_snapshot.ps1 restore <name> [-Yes]
#   powershell -ExecutionPolicy Bypass -File scripts\db_snapshot.ps1 list
#
# Writes data\snapshots\<name>.dump (pg_dump custom format) and <name>.files.tar.gz, the same
# files as db_snapshot.sh. data\ is git-ignored, so snapshots never go in git.
#
# Settings (environment): DB_CONTAINER (koyla-db), API_CONTAINER (koyla-api),
# WORKER_CONTAINER (koyla-worker), FILES_VOLUME (read from the api container's /data/files
# mount), POSTGRES_USER / POSTGRES_DB (from .env, else koyla).
param(
    [Parameter(Position = 0)][ValidateSet("create", "restore", "list")][string]$Command = "list",
    [Parameter(Position = 1)][string]$Name = "",
    [switch]$Yes
)
# Not "Stop": Windows PowerShell would then treat any docker message on stderr as a failure.
# Failures are caught from exit codes instead (see Invoke-Docker below).
$ErrorActionPreference = "Continue"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$SnapDir = "data\snapshots"
$Helper = "koyla-snapshot-helper"

function Setting([string]$name, [string]$default) {
    $v = [Environment]::GetEnvironmentVariable($name)
    if ($v) { return $v }
    return $default
}
function EnvFileValue([string]$key) {
    if (-not (Test-Path ".env")) { return $null }
    $line = Get-Content ".env" | Where-Object { $_ -match "^$key=" } | Select-Object -Last 1
    if ($line) { return ($line -replace "^$key=", "").Trim() }
    return $null
}

$DbContainer = Setting "DB_CONTAINER" "koyla-db"
$ApiContainer = Setting "API_CONTAINER" "koyla-api"
$WorkerContainer = Setting "WORKER_CONTAINER" "koyla-worker"
$PgUser = Setting "POSTGRES_USER" (EnvFileValue "POSTGRES_USER")
if (-not $PgUser) { $PgUser = "koyla" }
$PgDb = Setting "POSTGRES_DB" (EnvFileValue "POSTGRES_DB")
if (-not $PgDb) { $PgDb = "koyla" }

function Say([string]$text) { Write-Host ""; Write-Host "==> $text" }
function Fail([string]$text) { Write-Host "Error: $text" -ForegroundColor Red; exit 1 }

# Runs docker and stops on a non-zero exit code (native commands do not throw by themselves).
function Invoke-Docker {
    & docker @args
    if ($LASTEXITCODE -ne 0) { throw "docker $($args -join ' ') failed (exit $LASTEXITCODE)" }
}

function Running([string]$container) {
    $state = & docker inspect -f "{{.State.Running}}" $container 2>$null
    $global:LASTEXITCODE = 0
    return ($state -eq "true")
}

function FilesVolume {
    $v = [Environment]::GetEnvironmentVariable("FILES_VOLUME")
    if ($v) { return $v }
    foreach ($c in @($ApiContainer, $WorkerContainer)) {
        # Go template raw string (backquotes): Windows PowerShell drops double quotes inside
        # arguments it passes to other programs.
        $v = & docker inspect -f '{{range .Mounts}}{{if eq .Destination `/data/files`}}{{.Name}}{{end}}{{end}}' $c 2>$null
        $global:LASTEXITCODE = 0
        if ($v) { return "$v".Trim() }
    }
    # docker compose names volumes <project>_<volume>; the project is the folder name.
    $project = ((Split-Path -Leaf $Root).ToLower() -replace "[^a-z0-9_-]", "")
    return "${project}_files"
}

# A short-lived container with the files volume mounted, for tar and docker cp.
function Start-Helper([string]$volume) {
    $image = (& docker inspect -f "{{.Config.Image}}" $DbContainer).Trim()
    & docker rm -f $Helper 2>$null | Out-Null
    $global:LASTEXITCODE = 0
    Invoke-Docker run -d --name $Helper -v "${volume}:/data/files" --entrypoint sleep $image 3600 | Out-Null
}
function Stop-Helper {
    & docker rm -f $Helper 2>$null | Out-Null
    $global:LASTEXITCODE = 0
}

function Check-Name([string]$n) {
    if ($n -notmatch "^[A-Za-z0-9._-]+$") { Fail "a snapshot name may only use letters, digits, '.', '_' and '-'" }
}

function Need-Db {
    # Used unquoted in SQL below (quotes inside arguments do not survive Windows PowerShell).
    if ("$PgDb$PgUser" -notmatch "^[A-Za-z0-9_]+$") { Fail "POSTGRES_DB and POSTGRES_USER may only use letters, digits and '_'" }
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Fail "docker was not found" }
    if (-not (Running $DbContainer)) { Fail "the database container '$DbContainer' is not running (docker compose up -d db)" }
}

function New-Snapshot([string]$n) {
    if (-not $n) { $n = "demo-" + (Get-Date -Format "yyyyMMdd-HHmm") }
    Check-Name $n
    Need-Db
    New-Item -ItemType Directory -Force $SnapDir | Out-Null
    $dump = Join-Path $SnapDir "$n.dump"
    $files = Join-Path $SnapDir "$n.files.tar.gz"
    if ((Test-Path $dump) -or (Test-Path $files)) { Fail "snapshot '$n' already exists in $SnapDir" }

    Say "Dumping database '$PgDb' from $DbContainer"
    # Dump inside the container and copy the file out: PowerShell would damage a binary dump
    # passed through a pipe.
    Invoke-Docker exec $DbContainer pg_dump -U $PgUser -d $PgDb -Fc -f /tmp/snapshot.dump
    Invoke-Docker cp "${DbContainer}:/tmp/snapshot.dump" $dump
    Invoke-Docker exec $DbContainer rm -f /tmp/snapshot.dump

    $volume = FilesVolume
    & docker volume inspect $volume 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail "files volume '$volume' not found (set FILES_VOLUME)" }
    Say "Packing files volume '$volume'"
    try {
        Start-Helper $volume
        Invoke-Docker exec $Helper tar czf /tmp/files.tar.gz -C /data/files .
        Invoke-Docker cp "${Helper}:/tmp/files.tar.gz" $files
    } finally {
        Stop-Helper
    }

    Say "Saved snapshot '$n'"
    Get-Item $dump, $files | Format-Table Name, @{ Label = "Size (KB)"; Expression = { [math]::Ceiling($_.Length / 1KB) } } -AutoSize
}

function Restore-Snapshot([string]$n) {
    if (-not $n) { Fail "name the snapshot to restore (scripts\db_snapshot.ps1 list)" }
    Check-Name $n
    $dump = Join-Path $SnapDir "$n.dump"
    $files = Join-Path $SnapDir "$n.files.tar.gz"
    if (-not (Test-Path $dump)) { Fail "$dump not found (scripts\db_snapshot.ps1 list)" }
    $hasFiles = Test-Path $files
    if (-not $hasFiles) { Write-Host "Note: $files not found; only the database will be restored." }
    Need-Db
    $volume = FilesVolume

    if (-not $Yes) {
        Write-Host "This REPLACES database '$PgDb' in $DbContainer and every file in volume '$volume'"
        Write-Host "with snapshot '$n'. Anything added since that snapshot is lost."
        $answer = Read-Host "Type yes to continue"
        if ($answer -ne "yes") { Fail "cancelled, nothing changed" }
    }

    # The api and worker hold database connections and write files; pause them meanwhile.
    $paused = @()
    foreach ($c in @($WorkerContainer, $ApiContainer)) {
        if (Running $c) {
            Invoke-Docker stop $c | Out-Null
            $paused += $c
        }
    }
    try {
        Say "Recreating database '$PgDb'"
        Invoke-Docker exec $DbContainer psql -U $PgUser -d postgres -v ON_ERROR_STOP=1 -q `
            -c "DROP DATABASE IF EXISTS $PgDb WITH (FORCE)" `
            -c "CREATE DATABASE $PgDb OWNER $PgUser"
        Invoke-Docker cp $dump "${DbContainer}:/tmp/snapshot.dump"
        Say "Restoring the dump"
        Invoke-Docker exec $DbContainer pg_restore -U $PgUser -d $PgDb --no-owner --exit-on-error /tmp/snapshot.dump
        Invoke-Docker exec $DbContainer rm -f /tmp/snapshot.dump

        if ($hasFiles) {
            Say "Restoring files volume '$volume'"
            & docker volume inspect $volume 2>$null | Out-Null
            if ($LASTEXITCODE -ne 0) { Invoke-Docker volume create $volume | Out-Null }
            try {
                Start-Helper $volume
                Invoke-Docker cp $files "${Helper}:/tmp/files.tar.gz"
                Invoke-Docker exec $Helper sh -c "find /data/files -mindepth 1 -delete && tar xzf /tmp/files.tar.gz -C /data/files"
            } finally {
                Stop-Helper
            }
        }
    } finally {
        foreach ($c in $paused) {
            & docker start $c | Out-Null
            if ($LASTEXITCODE -eq 0) { Write-Host "Started $c again" }
        }
    }
    # The api runs "alembic upgrade head" when it starts, so an older snapshot is migrated then.
    Say "Restored snapshot '$n'"
}

function Show-Snapshots {
    $items = @(Get-ChildItem $SnapDir -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "\.(dump|files\.tar\.gz)$" })
    if (-not $items.Count) {
        Write-Host "No snapshots in $SnapDir yet (scripts\db_snapshot.ps1 create)."
        return
    }
    $items | Sort-Object Name | Format-Table Name, LastWriteTime, @{ Label = "Size (KB)"; Expression = { [math]::Ceiling($_.Length / 1KB) } } -AutoSize
}

switch ($Command) {
    "create" { New-Snapshot $Name }
    "restore" { Restore-Snapshot $Name }
    "list" { Show-Snapshots }
}
