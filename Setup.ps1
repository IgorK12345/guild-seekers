$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Unable to create Python environment' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Unable to install dependencies' }
New-Item -ItemType Directory -Force '.runtime' | Out-Null
if (-not (Test-Path '.runtime\pgsql\bin\postgres.exe')) {
    $download = Join-Path $PSScriptRoot '.runtime\postgresql.zip'
    Invoke-WebRequest -Uri 'https://get.enterprisedb.com/postgresql/postgresql-17.11-3-windows-x64-binaries.zip' -OutFile $download
    if ((Get-FileHash -LiteralPath $download -Algorithm SHA256).Hash -ne '4b8db0930c38f6ef845db919551dedda3b6b845aeb0927b3d79a6e8e9e4537cf') {
        throw 'PostgreSQL archive checksum mismatch'
    }
    & '.\.venv\Scripts\python.exe' -c "import zipfile; z=zipfile.ZipFile('.runtime/postgresql.zip'); z.extractall('.runtime',members=[n for n in z.namelist() if n.startswith(('pgsql/bin/','pgsql/lib/','pgsql/share/'))])"
    if ($LASTEXITCODE -ne 0) { throw 'Unable to unpack PostgreSQL' }
}
& '.\.venv\Scripts\python.exe' -X utf8 scripts/local.py
if ($LASTEXITCODE -ne 0) { throw 'Unable to start game' }
