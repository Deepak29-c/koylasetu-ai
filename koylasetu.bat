<# : KoylaSetu AI - one file to start or stop the whole app on Windows. Double-click it.
@echo off
set "KOYLA_BAT=%~f0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-Expression (Get-Content -Raw -LiteralPath $env:KOYLA_BAT)"
exit /b
#>
# (The lines above let Windows run this .bat file as PowerShell. Windows PowerShell 5.1+.)
#
# START (press Enter): database -> Ollama + the models in .env -> API :8000 -> website :3000,
#   then opens the browser. Anything already running is left alone. After a git pull it
#   installs changed Python / npm packages and updates the database schema.
#   First run on a fresh clone: creates .env and backend\.venv, installs a portable
#   Postgres 16 + pgvector into .localdev\ (git-ignored), creates and seeds the database.
#   If .env already points to a running Postgres (e.g. Docker's), that one is used.
# STOP (type S): website, API and the .localdev database. Ollama keeps running.
#
# Needs: Python 3.11+ (py launcher), Node.js 20+, Ollama. Optional: Tesseract (scanned PDFs).

# 'Continue': Windows PowerShell 5.1 turns any stderr line of a program (alembic's INFO lines,
# pip notices) into a fatal error under 'Stop'. Every step checks its exit code instead.
$ErrorActionPreference = 'Continue'
$Root   = Split-Path -Parent $env:KOYLA_BAT
$Dev    = Join-Path $Root '.localdev'
$Logs   = Join-Path $Dev 'logs'
$PgBin  = Join-Path $Dev 'pgsql\bin'
$PgData = Join-Path $Dev 'pgdata'
$Py     = Join-Path $Root 'backend\.venv\Scripts\python.exe'
$EnvFile = Join-Path $Root '.env'
$Tess   = 'C:\Program Files\Tesseract-OCR'
New-Item -ItemType Directory -Force $Logs | Out-Null
Set-Location $Root

function Say($m)  { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "    OK   $m" -ForegroundColor Green }
function Warn($m) { Write-Host "    !    $m" -ForegroundColor Yellow }
function Test-Url($url) {
    try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 $url).StatusCode -lt 500 } catch { $false }
}
function Wait-Url($url, $seconds) {
    $end = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $end) {
        if (Test-Url $url) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}
function Test-Port($hostName, $port) {
    try {
        $client = New-Object Net.Sockets.TcpClient
        $attempt = $client.BeginConnect($hostName, $port, $null, $null)
        $open = $attempt.AsyncWaitHandle.WaitOne(1500)
        if ($open) { $client.EndConnect($attempt) }
        $client.Close()
        return $open
    } catch { return $false }
}
function Read-EnvValue($key, $default) {
    $line = Get-Content $EnvFile -ErrorAction SilentlyContinue |
        Where-Object { $_ -match "^\s*$key\s*=" } | Select-Object -First 1
    if ($line) { return (($line -split '=', 2)[1] -split '#')[0].Trim() }
    return $default
}
function Find-Python($versions) {
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) { return $null }
    foreach ($v in $versions) {
        & py "-$v" -c "import sys" *> $null
        if ($LASTEXITCODE -eq 0) { return "-$v" }
    }
    return $null
}
function Start-Window($title, $workDir, $command, $pidFile) {
    $full = "`$host.UI.RawUI.WindowTitle = '$title'; Set-Location '$workDir'; $command"
    $p = Start-Process powershell -ArgumentList '-NoProfile', '-NoExit', '-Command', $full `
        -WindowStyle Minimized -PassThru
    Set-Content -Path (Join-Path $Dev $pidFile) -Value $p.Id
}
function Pg-Ready($port) {
    & "$PgBin\pg_isready.exe" -h 127.0.0.1 -p $port *> $null
    return ($LASTEXITCODE -eq 0)
}
function Start-LocalPostgres($port) {
    Remove-Item (Join-Path $PgData 'postmaster.pid') -ErrorAction SilentlyContinue
    Start-Process "$PgBin\pg_ctl.exe" -WindowStyle Hidden -ArgumentList `
        'start', '-D', "`"$PgData`"", '-o', "`"-h 127.0.0.1 -p $port`"", '-l', "`"$Logs\postgres.log`""
    foreach ($i in 1..30) { Start-Sleep -Seconds 1; if (Pg-Ready $port) { return } }
    throw "Postgres did not start - see $Logs\postgres.log"
}

# --- first-run setup ----------------------------------------------------------------------

function New-LocalEnv {
    # .env for this machine: localhost services, no Redis (INGEST_INLINE), random JWT secret.
    $bytes = New-Object byte[] 32
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $secret = ($bytes | ForEach-Object { $_.ToString('x2') }) -join ''
    $set = [ordered]@{
        DATABASE_URL        = 'postgresql+psycopg://koyla:koyla@127.0.0.1:55432/koyla'
        REDIS_URL           = 'redis://localhost:6379/0'
        STORAGE_DIR         = ((Join-Path $Dev 'storage') -replace '\\', '/')
        LLM_BASE_URL        = 'http://127.0.0.1:11434'
        OCR_ENGINE          = 'tesseract'
        INGEST_INLINE       = 'true'
        JWT_SECRET          = $secret
        CORS_ORIGINS        = 'http://localhost:3000,http://127.0.0.1:3000'
        NEXT_PUBLIC_API_URL = 'http://127.0.0.1:8000'
    }
    $out = New-Object System.Collections.Generic.List[string]
    foreach ($line in Get-Content (Join-Path $Root '.env.example')) {
        $key = ($line -split '=', 2)[0].Trim()
        if ($line -match '=' -and $set.Contains($key)) { $out.Add("$key=$($set[$key])"); $set.Remove($key) }
        else { $out.Add($line) }
    }
    foreach ($key in $set.Keys) { $out.Add("$key=$($set[$key])") }
    [IO.File]::WriteAllLines($EnvFile, $out, (New-Object Text.UTF8Encoding $false))
}

function Install-PortablePostgres {
    # Postgres 16 + pgvector for Windows, from the pgserver Python package (no admin rights).
    $pyVer = Find-Python @('3.12', '3.11', '3.10')
    if (-not $pyVer) { throw "Installing the local database needs Python 3.10-3.12 (py launcher). Install Python 3.12 from python.org, or point DATABASE_URL in .env at a Postgres with pgvector." }
    $venv = Join-Path $Dev 'pgvenv'
    & py $pyVer -m venv $venv
    & "$venv\Scripts\python.exe" -m pip install -q pgserver
    if ($LASTEXITCODE -ne 0) { throw "could not download the portable Postgres (pip install pgserver)" }
    $install = & "$venv\Scripts\python.exe" -c "import pgserver, os; print(os.path.join(os.path.dirname(pgserver.__file__), 'pginstall'))"
    Copy-Item -Recurse -Force $install.Trim() (Join-Path $Dev 'pgsql')
    Remove-Item -Recurse -Force $venv -ErrorAction SilentlyContinue
}

function Ensure-Setup($dbHost, $dbPort) {
    if (-not (Test-Path $Py)) {
        Say "First run: Python environment for the API (a few minutes)"
        $pyVer = Find-Python @('3.13', '3.12', '3.11')
        if (-not $pyVer) { throw "Python 3.11+ not found. Install it from python.org (tick 'py launcher')." }
        & py $pyVer -m venv (Join-Path $Root 'backend\.venv')
        & $Py -m pip install -q -r (Join-Path $Root 'backend\requirements.txt')
        if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
        Set-Content (Join-Path $Dev 'requirements.sha') (Get-FileHash (Join-Path $Root 'backend\requirements.txt')).Hash
        Ok "backend\.venv ready"
    }
    $feEnv = Join-Path $Root 'frontend\.env.local'
    if (-not (Test-Path $feEnv)) {
        $api = Read-EnvValue 'NEXT_PUBLIC_API_URL' 'http://127.0.0.1:8000'
        [IO.File]::WriteAllLines($feEnv, @("NEXT_PUBLIC_API_URL=$api"), (New-Object Text.UTF8Encoding $false))
    }
    if ((Test-Path $PgData) -or (Test-Port $dbHost $dbPort)) { return }
    Say "First run: local database (Postgres 16 + pgvector in .localdev)"
    if (-not (Test-Path $PgBin)) { Install-PortablePostgres; Ok "portable Postgres installed" }
    & "$PgBin\initdb.exe" -D $PgData -U postgres -A trust -E UTF8 *> (Join-Path $Logs 'initdb.log')
    if ($LASTEXITCODE -ne 0) { throw "initdb failed - see $Logs\initdb.log" }
    Start-LocalPostgres $dbPort
    & $Py (Join-Path $Root 'scripts\setup_local_db.py') --admin-url "postgresql://postgres@127.0.0.1:$dbPort/postgres" --seed --skip-redis
    if ($LASTEXITCODE -ne 0) { throw "database setup failed (see messages above)" }
    Ok "database created, migrated and seeded with demo users"
}

# --- stop / start ---------------------------------------------------------------------------

function Stop-All {
    Write-Host "`nStopping KoylaSetu AI..." -ForegroundColor White
    foreach ($f in 'web.pid', 'api.pid') {
        $file = Join-Path $Dev $f
        if (Test-Path $file) {
            & taskkill /PID (Get-Content $file) /T /F *> $null
            Remove-Item $file
        }
    }
    Get-CimInstance Win32_Process | Where-Object {
        ($_.CommandLine -like '*uvicorn app.main:app*' -and $_.CommandLine -like "*$Root*") -or
        ($_.Name -eq 'node.exe' -and $_.CommandLine -like "*$Root*frontend*")
    } | ForEach-Object { & taskkill /PID $_.ProcessId /T /F *> $null }
    Ok "website and API stopped"
    if (Test-Path $PgData) {
        & "$PgBin\pg_ctl.exe" stop -D $PgData -m fast *> $null
        Ok "database stopped"
    }
}

function Start-All {
    Write-Host "`nKoylaSetu AI - starting everything" -ForegroundColor White
    if (-not (Test-Path $EnvFile)) { New-LocalEnv; Ok "created .env with local settings" }
    $dbUrl = Read-EnvValue 'DATABASE_URL' ''
    $dbHost = '127.0.0.1'; $dbPort = 55432
    if ($dbUrl -match '@([^:/@]+):(\d+)/') { $dbHost = $matches[1]; $dbPort = [int]$matches[2] }
    Ensure-Setup $dbHost $dbPort

    Say "Database ($dbHost`:$dbPort)"
    if (Test-Path $PgData) {
        if (Pg-Ready $dbPort) { Ok "already running" } else { Start-LocalPostgres $dbPort; Ok "started" }
    } elseif (Test-Port $dbHost $dbPort) {
        Ok "using the database from .env"
    } else {
        throw "no database at $dbHost`:$dbPort (DATABASE_URL in .env)"
    }

    $llm   = Read-EnvValue 'LLM_MODEL' 'qwen2.5:3b-instruct'
    $embed = Read-EnvValue 'EMBED_MODEL' 'bge-m3'
    Say "AI model server (Ollama: $llm + $embed)"
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) { throw "Ollama is not installed. Install it: winget install Ollama.Ollama (then run this again)" }
    if (Test-Url 'http://127.0.0.1:11434/api/version') {
        Ok "already running"
    } else {
        $app = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama app.exe'
        if (Test-Path $app) { Start-Process $app } else { Start-Process ollama -ArgumentList 'serve' -WindowStyle Hidden }
        if (-not (Wait-Url 'http://127.0.0.1:11434/api/version' 60)) { throw "Ollama did not start" }
        Ok "started"
    }
    $have = (ollama list) -join "`n"
    foreach ($m in @($llm, $embed)) {
        $name = $m
        if ($name -notmatch ':') { $name = "${name}:latest" }
        if ($have -match [regex]::Escape($name)) {
            Ok "model $m is ready"
        } else {
            Warn "model $m is missing - downloading (one time, a few GB)..."
            ollama pull $m
            if ($LASTEXITCODE -ne 0) { throw "could not download $m" }
            Ok "model $m downloaded"
        }
    }
    if (-not (Test-Path "$Tess\tesseract.exe") -and -not (Get-Command tesseract -ErrorAction SilentlyContinue)) {
        Warn "Tesseract not found: scanned PDFs can't be read (winget install UB-Mannheim.TesseractOCR)"
    }

    Say "API (http://127.0.0.1:8000)"
    if (Test-Url 'http://127.0.0.1:8000/health') {
        Ok "already running"
    } else {
        $req = Join-Path $Root 'backend\requirements.txt'
        $stamp = Join-Path $Dev 'requirements.sha'
        $hash = (Get-FileHash $req).Hash
        if (-not (Test-Path $stamp) -or (Get-Content $stamp) -ne $hash) {
            Warn "requirements.txt changed - installing Python packages..."
            & $Py -m pip install -q -r $req
            if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
            Set-Content $stamp $hash
        }
        Push-Location (Join-Path $Root 'backend')
        & $Py -m alembic upgrade head *> (Join-Path $Logs 'migrate.log')
        $migrated = $LASTEXITCODE
        Pop-Location
        if ($migrated -ne 0) { throw "database migration failed - see $Logs\migrate.log" }
        Ok "database schema up to date"
        $cmd = "`$env:Path += ';$Tess'; & '$Py' -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
        Start-Window 'KoylaSetu API' (Join-Path $Root 'backend') $cmd 'api.pid'
        if (-not (Wait-Url 'http://127.0.0.1:8000/health' 90)) { throw "API did not start - open the 'KoylaSetu API' window to see why" }
        Ok "started"
    }

    Say "Website (http://localhost:3000)"
    if (Test-Url 'http://localhost:3000/login') {
        Ok "already running"
    } else {
        if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw "Node.js is not installed. Install it: winget install OpenJS.NodeJS.LTS (then run this again)" }
        $fe = Join-Path $Root 'frontend'
        $lock = Join-Path $fe 'package-lock.json'
        $installed = Join-Path $fe 'node_modules\.package-lock.json'
        if (-not (Test-Path $installed) -or (Get-Item $lock).LastWriteTime -gt (Get-Item $installed).LastWriteTime) {
            Warn "installing website packages (npm ci)..."
            Push-Location $fe
            npm ci --no-audit --no-fund
            $npmOk = $LASTEXITCODE
            Pop-Location
            if ($npmOk -ne 0) { throw "npm ci failed" }
        }
        Start-Window 'KoylaSetu Website' $fe 'npm run dev' 'web.pid'
        if (-not (Wait-Url 'http://localhost:3000/login' 180)) { throw "website did not start - open the 'KoylaSetu Website' window to see why" }
        Ok "started"
    }

    Start-Process 'http://localhost:3000'
    $password = Read-EnvValue 'SEED_DEMO_PASSWORD' 'change-me-too'
    Write-Host "`nKoylaSetu AI is running:  http://localhost:3000" -ForegroundColor Green
    Write-Host "  Login: analyst@koylasetu.local  /  $password   (admin@, reviewer@, approver@, operator@, viewer@ also work)"
    Write-Host "  AI model: $llm"
    Write-Host "  No documents yet? Upload some, or load the public set: scripts\fetch_sources.py then scripts\load_sources.py"
    Write-Host "  To stop: double-click koylasetu.bat again and type S"
}

Write-Host "KoylaSetu AI" -ForegroundColor White
$choice = Read-Host "Press Enter to START, or type S and press Enter to STOP"
try {
    if ($choice -match '^\s*[sS]') { Stop-All } else { Start-All }
} catch {
    Write-Host "    FAIL $($_.Exception.Message)" -ForegroundColor Red
}
Read-Host "`nPress Enter to close this window"
