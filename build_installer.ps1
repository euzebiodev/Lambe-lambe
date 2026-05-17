$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    python -m venv .venv
}

& $python -m pip install -r requirements.txt
& $python -m pip install pyinstaller

if (Test-Path "dist") {
    Remove-Item -LiteralPath "dist" -Recurse -Force
}
if (Test-Path "build") {
    Remove-Item -LiteralPath "build" -Recurse -Force
}

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "AlbumPolaroid" `
    --collect-all "cv2" `
    --collect-all "webview" `
    --collect-submodules "clr_loader" `
    --collect-submodules "pythonnet" `
    "desktop_app.py"

$isccCandidates = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
)

$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    throw "ISCC.exe nao encontrado. Instale o Inno Setup 6 com: winget install --id JRSoftware.InnoSetup -e"
}

& $iscc ".\installer\AlbumPolaroid.iss"

Write-Host ""
Write-Host "Instalador criado em:" -ForegroundColor Green
Get-ChildItem ".\installer-output\*.exe" | Select-Object -ExpandProperty FullName
