$ErrorActionPreference = "SilentlyContinue"

$keys = @(
    "HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
    "HKCU:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
)

foreach ($key in $keys) {
    $runtime = Get-ItemProperty -Path $key
    if ($runtime -and $runtime.pv) {
        exit 0
    }
}

$installer = Join-Path $env:TEMP "MicrosoftEdgeWebView2Setup.exe"
Invoke-WebRequest -UseBasicParsing "https://go.microsoft.com/fwlink/p/?LinkId=2124703" -OutFile $installer

if (Test-Path $installer) {
    Start-Process -FilePath $installer -ArgumentList "/silent", "/install" -Wait
}

exit 0
